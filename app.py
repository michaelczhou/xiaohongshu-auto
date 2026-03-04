"""
小红书自动发布系统 - FastAPI 主程序
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import uvicorn
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

# 静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """生成单个内容"""
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
async def get_history(limit: int = 50):
    """获取历史记录"""
    return cache_manager.get_history(limit=limit)


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
