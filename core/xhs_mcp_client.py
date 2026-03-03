"""
小红书 MCP 客户端 - 与 MCP 服务通信
"""
import httpx
from typing import Dict, Optional


class XHSMCPClient:
    """小红书 MCP 客户端"""
    
    def __init__(self, mcp_url: str = "http://localhost:18060/mcp"):
        self.mcp_url = mcp_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            response = await self.client.get(self.mcp_url.replace("/mcp", "/health"))
            return response.status_code == 200
        except Exception:
            return False
    
    async def publish_note(self, title: str, content: str, tags: list, image_paths: list = None) -> Dict:
        """发布笔记到小红书"""
        try:
            response = await self.client.post(
                f"{self.mcp_url}/publish",
                json={
                    "title": title,
                    "content": content,
                    "tags": tags,
                    "images": image_paths or []
                }
            )
            return response.json()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def close(self):
        await self.client.aclose()
