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

from config.config_manager import config_manager, AppConfig
from core.content_generator import ContentGenerator
from cache.cache_manager import cache_manager

app = FastAPI(title="小红书自动发布系统", version="1.0.0")

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

# 全局生成器
generator = ContentGenerator()


class ConfigRequest(BaseModel):
    llm_api_key: str
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    jina_api_key: str = ""
    tavily_api_key: str = ""
    xhs_mcp_url: str = "http://localhost:18060/mcp"


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
        "xhs_mcp_url": config.xhs_mcp_url,
        "has_llm_key": bool(config.llm_api_key),
        "has_jina_key": bool(config.jina_api_key),
        "has_tavily_key": bool(config.tavily_api_key),
    }


@app.post("/api/config")
async def save_config(req: ConfigRequest):
    """保存配置"""
    config = AppConfig(**req.model_dump())
    config_manager.save(config)
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
