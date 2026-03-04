# 小红书自动发布系统 📕

[![GitHub](https://img.shields.io/github/stars/michaelczhou/xiaohongshu-auto?style=flat)](https://github.com/michaelczhou/xiaohongshu-auto)
[![License](https://img.shields.io/github/license/michaelczhou/xiaohongshu-auto)](https://github.com/michaelczhou/xiaohongshu-auto/blob/main/LICENSE)

基于 MCP (Model Context Protocol) 的智能内容生成和自动发布系统。

**在线 Demo**: 输入主题 → AI 自动搜索 → 生成内容 → 发布到小红书

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

| 项目 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 运行主程序 |
| Node.js | 16+ | MCP 工具 |
| 小红书账号 | - | 用于发布 |

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/michaelczhou/xiaohongshu-auto.git
cd xiaohongshu-auto

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动小红书 MCP 服务（必须）
git clone https://github.com/xpzouying/xiaohongshu-mcp.git
cd xiaohongshu-mcp
# 按该项目 README 配置小红书账号并启动服务

# 4. 启动本系统
cd ../xiaohongshu-auto
python app.py

# 访问 http://localhost:8080
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
