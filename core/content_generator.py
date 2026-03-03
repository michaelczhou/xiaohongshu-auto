"""
小红书内容生成器 - 基于 LLM 和 MCP 工具生成内容
"""
import json
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from ..config.config_manager import config_manager


class ContentGenerator:
    """内容生成器"""
    
    def __init__(self):
        self.config = config_manager.load()
        self.client = AsyncOpenAI(
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_base_url
        )
    
    async def search_info(self, topic: str, days: int = 7) -> Dict:
        """搜索相关信息"""
        # 这里会调用 MCP 工具进行搜索
        # 目前先返回空结果，后续集成 MCP
        return {
            "topic": topic,
            "articles": [],
            "images": []
        }
    
    async def generate_content(self, topic: str, search_results: Dict = None) -> Dict:
        """生成小红书内容"""
        prompt = f"""
请为以下主题生成一篇小红书笔记：

主题：{topic}

要求：
1. 标题：20 字以内，吸引眼球，使用 emoji
2. 正文：800-1200 字，年轻化活泼风格，适当使用 emoji
3. 标签：5 个精准话题标签（不带#号）
4. 配图建议：3-4 张相关图片的描述

请以 JSON 格式返回：
{{
    "title": "标题",
    "content": "正文内容",
    "tags": ["标签 1", "标签 2", "标签 3", "标签 4", "标签 5"],
    "image_prompts": ["图片 1 描述", "图片 2 描述", "图片 3 描述"]
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "你是小红书内容创作专家，擅长生成吸引人的笔记内容。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = json.loads(response.choices[0].message.content)
            return {
                "success": True,
                "data": content
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_and_publish(self, topic: str) -> Dict:
        """完整流程：搜索 → 生成 → 发布"""
        # 1. 搜索信息
        search_results = await self.search_info(topic)
        
        # 2. 生成内容
        gen_result = await self.generate_content(topic, search_results)
        
        if not gen_result["success"]:
            return gen_result
        
        # 3. 调用 MCP 发布（后续实现）
        # publish_result = await self.publish_to_xhs(gen_result["data"])
        
        return {
            "success": True,
            "topic": topic,
            "content": gen_result["data"],
            "status": "generated"  # 待发布
        }
