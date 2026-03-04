# 小红书自动发布系统 📕

[![GitHub](https://img.shields.io/github/stars/michaelczhou/xiaohongshu-auto?style=flat)](https://github.com/michaelczhou/xiaohongshu-auto)
[![License](https://img.shields.io/github/license/michaelczhou/xiaohongshu-auto)](https://github.com/michaelczhou/xiaohongshu-auto/blob/main/LICENSE)

基于 Playwright 浏览器自动化 + LLM 的智能小红书内容生成和自动发布系统。

**全自包含**：无需任何外部 MCP 服务依赖，所有功能（登录、发布、搜索、评论等）均在本项目内通过 Playwright 直接完成。

## 📁 项目结构

```
xiaohongshu-auto/
├── app.py               # FastAPI 主程序入口
├── config/              # 配置管理
│   └── config_manager.py
├── core/                # 核心功能
│   ├── browser_manager.py   # Playwright 浏览器生命周期管理
│   ├── xhs_actions.py       # 小红书页面操作（发布/搜索/评论等）
│   ├── xhs_service.py       # 统一服务层
│   └── content_generator.py # LLM 内容生成
├── web/                 # Web 界面
│   └── index.html
├── cache/               # 缓存和历史记录
├── cookies/             # 登录 Cookies 持久化
└── requirements.txt
```

## ✨ 功能

- 🔐 **扫码登录**：通过 Playwright 弹出浏览器扫码登录小红书
- 📝 **AI 内容生成**：输入主题，LLM 自动生成标题、正文、标签
- 🚀 **自动发布**：图文/视频笔记一键发布
- 🔍 **搜索笔记**：按关键词搜索小红书内容
- 💬 **评论互动**：自动评论、回复、点赞、收藏
- 📊 **批量操作**：支持多主题批量生成发布
- 🌐 **Web 界面**：美观的管理面板

## 🚀 快速开始

### 环境要求

| 项目 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 运行主程序 |
| Playwright | 最新 | 浏览器自动化 |
| 小红书账号 | - | 用于发布 |

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/michaelczhou/xiaohongshu-auto.git
cd xiaohongshu-auto

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 启动系统
python app.py

# 5. 访问 http://localhost:8080
```

### 首次使用

1. 打开 `http://localhost:8080`
2. 在「小红书账号」区域点击「扫码登录」
3. 在弹出的浏览器窗口中用小红书 APP 扫码
4. 登录成功后 Cookies 会自动保存，下次无需重新登录
5. 在配置区填写 LLM API Key
6. 输入主题，点击「生成并发布」

## 📋 配置说明

| 配置项 | 说明 | 必需 |
|--------|------|------|
| `LLM API Key` | 大模型 API 密钥 | ✅ |
| `LLM Base URL` | API 地址（默认 DashScope） | ✅ |
| `模型` | 使用的模型名称 | ✅ |
| `无头模式` | 是否隐藏浏览器窗口 | ❌ |

## ⚠️ 注意事项

- 首次运行需要**非无头模式**以扫码登录
- 登录成功后可切换为无头模式
- 请遵守小红书平台规则，合理使用
- Cookies 保存在 `cookies/` 目录，已加入 `.gitignore`
