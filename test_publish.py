"""
端到端测试：直接通过 MCP 协议发布一篇 OpenClaw 介绍文章到小红书
"""
import asyncio
import sys
sys.path.insert(0, "/Users/michaelzhou/project/vibecoding/xiaohongshu-auto")

from core.xhs_mcp_client import XHSMCPClient


# OpenClaw 介绍文章内容
TITLE = "🤖 OpenClaw：让AI帮你干活的神器"
CONTENT = """你还在手动重复做那些无聊的任务吗？🤯

今天给大家安利一个超酷的开源项目 ——  OpenClaw ✨

📌 什么是 OpenClaw？

OpenClaw 是一个 AI Agent 自动化平台，你可以把它理解为一个「AI 管家」🏠 只需要告诉它你想做什么，它就会自动调用各种工具帮你完成任务！

💡 它能做什么？

1️⃣ 自动化运营：社交媒体内容管理、定时发布
2️⃣ 数据采集：自动搜索、整理信息
3️⃣ 工作流编排：把多个 AI 工具串联起来，形成自动化流水线
4️⃣ 多平台集成：支持 Telegram、飞书、微信等多种渠道

🔥 为什么推荐？

✅ 开源免费，社区活跃
✅ 支持 MCP 协议，可以接入各种 AI 工具
✅ 部署简单，文档友好
✅ 适合个人开发者和小团队

🎯 适合谁用？

- 想要自动化运营的自媒体人
- 希望提高效率的开发者
- 对 AI Agent 感兴趣的技术爱好者

如果你也想让 AI 成为你的得力助手，赶紧去试试 OpenClaw 吧！💪

#OpenClaw #AI自动化 #效率工具 #开源项目 #AIAgent"""

TAGS = ["OpenClaw", "AI自动化", "效率工具", "开源项目", "AIAgent"]


async def main():
    client = XHSMCPClient("http://localhost:18060/mcp")
    
    try:
        # 1. 检查登录
        print("=" * 50)
        print("步骤 1: 检查登录状态...")
        login_result = await client.check_login()
        print(f"  结果: {login_result['text'] if login_result['success'] else login_result['error']}")
        
        if not login_result["success"] or "未登录" in login_result.get("text", ""):
            print("❌ 未登录，请先登录小红书")
            return
        
        # 2. 下载配图
        print("\n步骤 2: 准备配图...")
        import httpx
        import tempfile
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as dl:
                resp = await dl.get("https://picsum.photos/800/600")
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                tmp.write(resp.content)
                tmp.close()
                image_path = tmp.name
                print(f"  配图已下载: {image_path}")
        except Exception as e:
            print(f"  ⚠️ 配图下载失败: {e}，将无图发布")
            image_path = None
        
        # 3. 发布
        print(f"\n步骤 3: 发布文章...")
        print(f"  标题: {TITLE}")
        print(f"  标签: {TAGS}")
        print(f"  正文长度: {len(CONTENT)} 字")
        
        images = [image_path] if image_path else []
        result = await client.publish_note(
            title=TITLE,
            content=CONTENT,
            tags=TAGS,
            image_paths=images
        )
        
        print(f"\n{'=' * 50}")
        if result["success"]:
            print(f"✅ 发布成功！")
            print(f"  详情: {result['text']}")
        else:
            print(f"❌ 发布失败")
            print(f"  错误: {result.get('error', '未知错误')}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
