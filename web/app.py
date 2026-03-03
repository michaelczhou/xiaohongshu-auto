"""
小红书自动发布系统 - Web API
"""
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import uvicorn

# 导入本地模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_manager import config_manager, AppConfig
from core.content_generator import ContentGenerator
from cache.cache_manager import cache_manager

# 创建 FastAPI 应用
app = FastAPI(title="小红书自动发布系统", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"
static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# 内容生成器实例
generator = ContentGenerator()


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse("index.html", {"request": request})


# ==================== API 路由 ====================

class ConfigInput(BaseModel):
    llm_api_key: str
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    jina_api_key: str = ""
    tavily_api_key: str = ""
    xhs_mcp_url: str = "http://localhost:18060/mcp"


@app.get("/api/config")
async def get_config():
    """获取配置（隐藏敏感信息）"""
    config = config_manager.load()
    return {
        "llm_base_url": config.llm_base_url,
        "llm_model": config.llm_model,
        "xhs_mcp_url": config.xhs_mcp_url,
        "llm_api_key_set": bool(config.llm_api_key),
        "jina_api_key_set": bool(config.jina_api_key),
        "tavily_api_key_set": bool(config.tavily_api_key),
    }


@app.post("/api/config")
async def save_config(config_input: ConfigInput):
    """保存配置"""
    config = AppConfig(**config_input.model_dump())
    config_manager.save(config)
    return {"success": True, "message": "配置已保存"}


class GenerateRequest(BaseModel):
    topic: str
    use_batch: bool = False
    topics: List[str] = None


@app.post("/api/generate")
async def generate_content(req: GenerateRequest):
    """生成内容"""
    if req.use_batch and req.topics:
        # 批量生成
        tasks = [generator.generate_and_publish(topic) for topic in req.topics]
        results = await asyncio.gather(*tasks)
        return {"success": True, "results": results}
    else:
        # 单个生成
        result = await generator.generate_and_publish(req.topic)
        return {"success": True, "result": result}


@app.get("/api/history")
async def get_history(limit: int = 50, status: str = None):
    """获取历史记录"""
    history = cache_manager.get_history(limit=limit, status=status)
    return {"success": True, "history": history}


@app.get("/api/statistics")
async def get_statistics():
    """获取统计信息"""
    stats = cache_manager.get_statistics()
    return {"success": True, "statistics": stats}


@app.delete("/api/history/{task_id}")
async def delete_history(task_id: str):
    """删除历史记录"""
    # TODO: 实现删除逻辑
    return {"success": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
