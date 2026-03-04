"""
小红书自动发布系统 - FastAPI 主程序
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import uvicorn
import uuid
import re
from pathlib import Path
from contextlib import asynccontextmanager

from config.config_manager import config_manager, AppConfig
from core.content_generator import ContentGenerator
from core.xhs_service import XHSService
from cache.cache_manager import cache_manager


# 全局服务
xhs_service: XHSService = None
generator: ContentGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global xhs_service, generator
    config = config_manager.load()
    xhs_service = XHSService(headless=config.headless)
    generator = ContentGenerator(xhs_service=xhs_service)
    print(f"✅ 小红书服务已启动 (headless={config.headless})")
    yield
    # 关闭时清理浏览器
    if xhs_service:
        await xhs_service.close()
        print("🛑 浏览器已关闭")


app = FastAPI(title="小红书自动发布系统", version="2.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 & 上传目录
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


class ConfigRequest(BaseModel):
    llm_api_key: str
    llm_base_url: str = "https://coding.dashscope.aliyuncs.com/v1"
    llm_model: str = "qwen3.5-plus"
    jina_api_key: str = ""
    tavily_api_key: str = ""
    headless: bool = False


class GenerateRequest(BaseModel):
    topic: str


class BatchGenerateRequest(BaseModel):
    topics: List[str]


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页面"""
    index_file = Path(__file__).parent / "web" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return "<h1>小红书自动发布系统</h1><p>请访问 /web/index.html</p>"


@app.get("/api/config")
async def get_config():
    """获取配置（隐藏敏感信息）"""
    config = config_manager.load()
    return {
        "llm_base_url": config.llm_base_url,
        "llm_model": config.llm_model,
        "headless": config.headless,
        "has_llm_key": bool(config.llm_api_key),
        "has_jina_key": bool(config.jina_api_key),
        "has_tavily_key": bool(config.tavily_api_key),
    }


@app.post("/api/config")
async def save_config(req: ConfigRequest):
    """保存配置"""
    global xhs_service, generator
    config = AppConfig(**req.model_dump())
    config_manager.save(config)
    # 重新初始化服务（headless 可能变了）
    if xhs_service:
        await xhs_service.close()
    xhs_service = XHSService(headless=config.headless)
    generator = ContentGenerator(xhs_service=xhs_service)
    return {"success": True, "message": "配置已保存"}


async def _check_login() -> dict:
    """检查登录状态，未登录则返回错误 dict，已登录返回 None"""
    login = await xhs_service.check_login_status()
    if "未登录" in login.get("text", ""):
        return {"success": False, "error": "未登录小红书，请先在页面上方扫码登录"}
    return None


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """生成单个内容"""
    if err := await _check_login():
        return err
    result = await generator.generate_and_publish(req.topic)
    
    # 保存到历史
    if result["success"]:
        cache_manager.add_task({
            "topic": req.topic,
            "content": result.get("content", {}),
            "status": "success"
        })
    
    return result


@app.post("/api/batch-generate")
async def batch_generate(req: BatchGenerateRequest):
    """批量生成"""
    if err := await _check_login():
        return err
    results = []
    for topic in req.topics:
        result = await generator.generate_and_publish(topic)
        results.append(result)
        
        # 保存到历史
        if result["success"]:
            cache_manager.add_task({
                "topic": topic,
                "content": result.get("content", {}),
                "status": "success"
            })
        
        # 避免请求过快
        await asyncio.sleep(1)
    
    return {"results": results, "total": len(results)}


@app.get("/api/history")
async def get_history(limit: int = 50, status: str = None):
    """获取历史记录，可按状态过滤"""
    return cache_manager.get_history(limit=limit, status=status)


@app.get("/api/stats")
async def get_stats():
    """获取统计"""
    return cache_manager.get_statistics()


# ----------------------------------------------------------
# 小红书服务 API
# ----------------------------------------------------------

@app.get("/api/xhs/login-status")
async def login_status():
    """检查小红书登录状态"""
    result = await xhs_service.check_login_status()
    return result


@app.post("/api/xhs/login")
async def login():
    """获取登录二维码并等待扫码"""
    result = await xhs_service.get_login_qrcode()
    return result


@app.post("/api/xhs/logout")
async def logout():
    """退出登录（清除 cookies）"""
    result = await xhs_service.delete_cookies()
    return result


# ----------------------------------------------------------
# 手动发布 API
# ----------------------------------------------------------

def markdown_to_xhs(md_text: str) -> str:
    """将 Markdown 转为小红书纯文本格式"""
    text = md_text
    # 标题 → 加粗 emoji 风格
    text = re.sub(r'^### (.+)$', r'📌 \1', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'✨ \1', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'🔥 \1', text, flags=re.MULTILINE)
    # 加粗 / 斜体
    text = re.sub(r'\*\*(.+?)\*\*', r'「\1」', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 无序列表
    text = re.sub(r'^[\-\*] (.+)$', r'• \1', text, flags=re.MULTILINE)
    # 有序列表 → emoji 数字
    num_emojis = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
    def replace_ol(m):
        idx = int(m.group(1)) - 1
        emoji = num_emojis[idx] if 0 <= idx < len(num_emojis) else f'{m.group(1)}.'
        return f'{emoji} {m.group(2)}'
    text = re.sub(r'^(\d+)\. (.+)$', replace_ol, text, flags=re.MULTILINE)
    # 行内代码
    text = re.sub(r'`(.+?)`', r'「\1」', text)
    # 代码块 → 保留内容
    text = re.sub(r'```\w*\n([\s\S]*?)```', r'\1', text)
    # 链接
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1', text)
    # 图片标记移除
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # 分割线
    text = re.sub(r'^---+$', '—————————', text, flags=re.MULTILINE)
    # 引用
    text = re.sub(r'^> (.+)$', r'💬 \1', text, flags=re.MULTILINE)
    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@app.post("/api/upload")
async def upload_images(files: List[UploadFile] = File(...)):
    """上传图片，返回本地路径列表"""
    saved = []
    for f in files:
        ext = Path(f.filename).suffix or '.jpg'
        name = f"{uuid.uuid4().hex}{ext}"
        dest = uploads_dir / name
        content = await f.read()
        dest.write_bytes(content)
        saved.append({
            "filename": f.filename,
            "path": str(dest),
            "url": f"/uploads/{name}",
            "size": len(content),
        })
    return {"success": True, "files": saved}


@app.post("/api/manual-publish")
async def manual_publish(
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    image_paths: str = Form(""),
    convert_markdown: bool = Form(True),
):
    """手动发布：用户自定义标题、内容（支持 Markdown）、图片"""
    if err := await _check_login():
        return err
    # Markdown → 小红书格式
    final_content = markdown_to_xhs(content) if convert_markdown else content

    # 解析标签
    tag_list = [t.strip().lstrip('#') for t in tags.split(',') if t.strip()] if tags else []
    # 在正文末尾追加标签
    if tag_list:
        tag_text = ' '.join(f'#{t}' for t in tag_list)
        final_content = f"{final_content}\n\n{tag_text}"

    # 解析图片路径
    img_list = [p.strip() for p in image_paths.split(',') if p.strip()] if image_paths else []

    # 如果没有图片，下载随机图
    if not img_list:
        import tempfile, httpx
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as dl:
                resp = await dl.get("https://picsum.photos/800/600")
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                tmp.write(resp.content)
                tmp.close()
                img_list = [tmp.name]
        except Exception:
            pass

    result = await xhs_service.publish_content(
        title=title,
        content=final_content,
        images=img_list,
        tags=tag_list,
    )

    # 保存历史
    cache_manager.add_task({
        "topic": f"[手动] {title}",
        "content": {"title": title, "content": final_content[:200], "tags": tag_list},
        "status": "success" if result.get("success") else "failed",
    })

    return result


@app.post("/api/preview-markdown")
async def preview_markdown(content: str = Form(...)):
    """预览 Markdown 转换结果"""
    return {"success": True, "converted": markdown_to_xhs(content)}


class SearchRequest(BaseModel):
    keyword: str
    sort_by: str = "综合"
    note_type: str = "不限"


@app.post("/api/xhs/search")
async def search_feeds(req: SearchRequest):
    """搜索小红书笔记"""
    result = await xhs_service.search_feeds(req.keyword, req.sort_by, req.note_type)
    return result


@app.get("/api/xhs/feeds")
async def list_feeds():
    """获取推荐笔记"""
    result = await xhs_service.list_feeds()
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8080)
