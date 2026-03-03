# 小红书自动发布系统

基于 MCP (Model Context Protocol) 的智能内容生成和自动发布系统。

## 📁 项目结构

```
xiaohongshu-auto/
├── config/              # 配置文件
├── core/                # 核心功能
├── mcp/                 # MCP 服务
├── web/                 # Web 界面
└── cache/               # 缓存和历史记录
```

## 🚀 快速开始

### 前置条件

1. **Python 3.8+**
2. **Node.js 16+**
3. **小红书账号**（用于 MCP 服务登录）

### 安装步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动小红书 MCP 服务（需要单独配置）
git clone https://github.com/xpzouying/xiaohongshu-mcp.git
cd xiaohongshu-mcp
# 按该项目说明配置并启动

# 3. 启动本系统
python app.py
```

## 📋 需要的配置

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| `XHS_COOKIE` | 小红书登录 Cookie | 登录小红书后从浏览器获取 |
| `LLM_API_KEY` | 大模型 API 密钥 | OpenAI/DeepSeek 等 |
| `JINA_API_KEY` | Jina 搜索 API | https://jina.ai |
| `TAVILY_API_KEY` | Tavily 搜索 API | https://tavily.com |

## ⚠️ 重要提示

- 小红书 MCP 服务是**必须**的依赖
- 需要先在 MCP 服务中登录你的小红书账号
- 请遵守小红书平台规则，合理使用
