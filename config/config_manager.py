"""
配置管理器 - 负责加载和保存系统配置
"""
import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用配置"""
    llm_api_key: str = Field(default="", description="LLM API 密钥")
    llm_base_url: str = Field(default="https://coding.dashscope.aliyuncs.com/v1", description="LLM API 基础 URL")
    llm_model: str = Field(default="qwen3.5-plus", description="使用的模型")
    jina_api_key: str = Field(default="", description="Jina 搜索 API 密钥")
    tavily_api_key: str = Field(default="", description="Tavily 搜索 API 密钥")
    xhs_mcp_url: str = Field(default="http://localhost:18060/mcp", description="小红书 MCP 服务地址")


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = Path(__file__).parent
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "app_config.json"
        self._config: Optional[AppConfig] = None
    
    def load(self) -> AppConfig:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._config = AppConfig(**data)
        else:
            self._config = AppConfig()
        
        return self._config
    
    def save(self, config: AppConfig) -> None:
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
        self._config = config
    
    def get_mcp_servers_config(self) -> dict:
        """生成 MCP 服务器配置"""
        config = self.load()
        return {
            "mcpServers": {
                "jina": {
                    "command": "npx",
                    "args": ["-y", "jina-mcp-tools"],
                    "env": {
                        "JINA_API_KEY": config.jina_api_key
                    }
                },
                "tavily": {
                    "command": "npx",
                    "args": ["-y", "mcp-remote", f"https://mcp.tavily.com/mcp/?tavilyApiKey={config.tavily_api_key}"]
                },
                "xhs": {
                    "type": "streamable_http",
                    "url": config.xhs_mcp_url
                }
            }
        }


# 全局配置管理器实例
config_manager = ConfigManager()
