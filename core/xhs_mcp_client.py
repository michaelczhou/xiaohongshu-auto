"""
小红书 MCP 客户端 - 通过 MCP 协议与 xiaohongshu-mcp 服务通信
"""
import httpx
import json
from typing import Dict, Optional


class XHSMCPClient:
    """小红书 MCP 客户端（使用 Streamable HTTP MCP 协议）"""
    
    def __init__(self, mcp_url: str = "http://localhost:18060/mcp"):
        self.mcp_url = mcp_url
        self.client = httpx.AsyncClient(timeout=180.0)
        self.session_id: Optional[str] = None
        self._initialized = False
        self._req_id = 0
    
    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id
    
    async def _mcp_request(self, method: str, params: dict = None, is_notification: bool = False) -> Optional[Dict]:
        """发送 MCP JSON-RPC 请求"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        if not is_notification:
            payload["id"] = self._next_id()
        
        response = await self.client.post(self.mcp_url, json=payload, headers=headers)
        
        # 保存 session id
        sid = response.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
        
        if is_notification:
            return None
        
        content_type = response.headers.get("content-type", "")
        body = response.text
        
        # 处理 SSE (text/event-stream) 格式响应
        if "text/event-stream" in content_type or body.startswith("event:") or body.startswith("data:"):
            return self._parse_sse(body)
        
        # 普通 JSON 响应
        if body.strip():
            return response.json()
        return None
    
    def _parse_sse(self, body: str) -> Optional[Dict]:
        """解析 SSE 格式响应，提取最后一个 JSON-RPC 消息"""
        import json
        last_result = None
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    try:
                        parsed = json.loads(data_str)
                        if "result" in parsed or "error" in parsed:
                            last_result = parsed
                    except json.JSONDecodeError:
                        continue
        return last_result
    
    async def _ensure_initialized(self):
        """确保 MCP 会话已初始化"""
        if self._initialized:
            return
        
        # initialize
        result = await self._mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "xiaohongshu-auto", "version": "1.0"}
        })
        
        # initialized notification
        await self._mcp_request("notifications/initialized", is_notification=True)
        self._initialized = True
    
    async def call_tool(self, tool_name: str, arguments: dict = None) -> Dict:
        """调用 MCP 工具"""
        await self._ensure_initialized()
        
        params = {"name": tool_name}
        if arguments:
            params["arguments"] = arguments
        
        result = await self._mcp_request("tools/call", params)
        
        if result and "result" in result:
            content_list = result["result"].get("content", [])
            text_parts = [c.get("text", "") for c in content_list if c.get("type") == "text"]
            return {
                "success": True,
                "text": "\n".join(text_parts),
                "raw": result["result"]
            }
        elif result and "error" in result:
            return {
                "success": False,
                "error": result["error"].get("message", str(result["error"]))
            }
        return {"success": False, "error": "未知错误"}
    
    async def check_login(self) -> Dict:
        """检查登录状态"""
        return await self.call_tool("check_login_status")
    
    async def publish_note(self, title: str, content: str, tags: list = None, image_paths: list = None) -> Dict:
        """发布图文笔记到小红书"""
        args = {
            "title": title,
            "content": content,
            "images": image_paths or [],
        }
        if tags:
            args["tags"] = tags
        
        return await self.call_tool("publish_content", args)
    
    async def search_feeds(self, keyword: str) -> Dict:
        """搜索小红书内容"""
        return await self.call_tool("search_feeds", {"keyword": keyword})
    
    async def close(self):
        await self.client.aclose()
