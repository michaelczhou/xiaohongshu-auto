"""
小红书内容生成器 - 基于 LLM 和 MCP 工具生成内容
"""
import json
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from config.config_manager import config_manager
from core.xhs_mcp_client import XHSMCPClient


class ContentGenerator:
    """内容生成器"""
    
    def __init__(self):
        self.config = config_manager.load()
        self.client = None
        self.mcp_client = None
        self._init_clients()
    
    def _init_clients(self):
        """初始化客户端（配置变更时重新初始化）"""
        self.config = config_manager.load()
        if self.config.llm_api_key:
            self.client = AsyncOpenAI(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url
            )
        self.mcp_client = XHSMCPClient(mcp_url=self.config.xhs_mcp_url)
    
    async def search_info(self, topic: str, days: int = 7) -> Dict:
        """搜索相关信息"""
        try:
            result = await self.mcp_client.search_feeds(topic)
            return {
                "topic": topic,
                "search_result": result.get("text", ""),
                "success": result.get("success", False)
            }
        except Exception as e:
            return {
                "topic": topic,
                "search_result": "",
                "success": False,
                "error": str(e)
            }
    
    async def generate_content(self, topic: str, search_results: Dict = None) -> Dict:
        """生成小红书内容"""
        if not self.client:
            self._init_clients()
            if not self.client:
                return {"success": False, "error": "未配置 LLM API Key，请先在设置中配置"}
        
        search_context = ""
        if search_results and search_results.get("success"):
            search_context = f"\n\n参考资料（来自小红书搜索结果）：\n{search_results.get('search_result', '')[:2000]}"
        
        prompt = f"""
请为以下主题生成一篇小红书笔记：

主题：{topic}
{search_context}

要求：
1. 标题：20 字以内，吸引眼球，使用 emoji
2. 正文：500-1000 字，年轻化活泼风格，适当使用 emoji
3. 标签：5 个精准话题标签（不带#号）
4. 正文末尾用 #标签 格式列出所有标签

请以 JSON 格式返回：
{{
    "title": "标题",
    "content": "正文内容（末尾包含 #标签）",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "你是小红书内容创作专家，擅长生成吸引人的笔记内容。请只返回 JSON，不要包含 markdown 代码块标记。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            content = json.loads(raw_content)
            return {
                "success": True,
                "data": content
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def publish_to_xhs(self, content_data: Dict, image_paths: list = None) -> Dict:
        """通过 MCP 发布到小红书"""
        title = content_data.get("title", "")
        content = content_data.get("content", "")
        tags = content_data.get("tags", [])
        
        # 如果没有提供图片，先下载一张随机图片
        if not image_paths:
            import tempfile
            import httpx as hx
            try:
                async with hx.AsyncClient(timeout=30, follow_redirects=True) as dl_client:
                    resp = await dl_client.get("https://picsum.photos/800/600")
                    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    tmp_file.write(resp.content)
                    tmp_file.close()
                    image_paths = [tmp_file.name]
            except Exception:
                image_paths = []
        
        result = await self.mcp_client.publish_note(
            title=title,
            content=content,
            tags=tags,
            image_paths=image_paths
        )
        return result
    
    async def generate_and_publish(self, topic: str, auto_publish: bool = True) -> Dict:
        """完整流程：搜索 → 生成 → 发布"""
        self._init_clients()
        
        # 1. 搜索信息（非必须，失败也继续）
        search_results = await self.search_info(topic)
        
        # 2. 生成内容
        gen_result = await self.generate_content(topic, search_results)
        
        if not gen_result["success"]:
            return gen_result
        
        # 3. 发布到小红书
        if auto_publish:
            publish_result = await self.publish_to_xhs(gen_result["data"])
            return {
                "success": publish_result.get("success", False),
                "topic": topic,
                "content": gen_result["data"],
                "publish_result": publish_result.get("text", publish_result.get("error", "")),
                "status": "published" if publish_result.get("success") else "publish_failed"
            }
        
        return {
            "success": True,
            "topic": topic,
            "content": gen_result["data"],
            "status": "generated"
        }
