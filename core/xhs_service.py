"""
小红书服务层 - 管理浏览器生命周期，对外提供统一的业务接口
替代原 Go 项目的 service.go
"""
import asyncio
from typing import Dict, List, Optional
from core.browser_manager import BrowserManager
from core.xhs_actions import XHSActions


class XHSService:
    """小红书服务（统一入口）"""

    def __init__(self, headless: bool = True):
        self.browser_mgr = BrowserManager(headless=headless)

    async def _run_action(self, action_func):
        """通用操作执行器：创建页面 → 执行 → 关闭页面"""
        page = await self.browser_mgr.new_page()
        try:
            actions = XHSActions(page)
            return await action_func(actions)
        finally:
            await page.close()

    # ----------------------------------------------------------
    # 登录
    # ----------------------------------------------------------
    async def check_login_status(self) -> Dict:
        result = await self._run_action(lambda a: a.check_login_status())
        if result.get("logged_in"):
            return {"success": True, "text": f"✅ 已登录\n用户名: {result.get('username', 'unknown')}\n\n你可以使用其他功能了。"}
        return {"success": True, "text": "❌ 未登录\n\n请先使用 get_login_qrcode 获取二维码登录。"}

    async def check_creator_login(self) -> Dict:
        """检查创作者中心（creator.xiaohongshu.com）是否已登录"""
        result = await self._run_action(lambda a: a.check_creator_login())
        return result

    async def get_login_qrcode(self) -> Dict:
        page = await self.browser_mgr.new_page()
        try:
            actions = XHSActions(page)
            result = await actions.get_login_qrcode()
            if result.get("success"):
                # 等待扫码
                login_result = await actions.wait_for_login(timeout=120)
                if login_result.get("success"):
                    await self.browser_mgr.save_cookies()
                    return {"success": True, "text": "✅ 登录成功！Cookies 已保存。"}
                return {"success": False, "text": "⏰ 登录超时，请重试。", "qrcode": result.get("qrcode")}
            return {"success": False, "text": result.get("error", "获取二维码失败")}
        finally:
            await page.close()

    async def delete_cookies(self) -> Dict:
        self.browser_mgr.delete_cookies()
        await self.browser_mgr.close()
        return {"success": True, "text": "✅ Cookies 已删除，需要重新登录。"}

    # ----------------------------------------------------------
    # 发布
    # ----------------------------------------------------------
    async def publish_content(
        self, title: str, content: str, images: List[str],
        tags: List[str] = None, is_original: bool = False,
        visibility: str = "公开可见",
    ) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.publish_content(
                title=title, content=content, image_paths=images,
                tags=tags, is_original=is_original, visibility=visibility,
            )
        result = await self._run_action(_do)
        if result.get("success"):
            data = result.get("data", {})
            return {
                "success": True,
                "text": f"内容发布成功: Title:{data.get('title','')} Images:{data.get('images_count',0)} Status:{data.get('status','')}"
            }
        return {"success": False, "text": result.get("error", "发布失败")}

    async def publish_video(
        self, title: str, content: str, video: str,
        tags: List[str] = None, visibility: str = "公开可见",
    ) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.publish_video(
                title=title, content=content, video_path=video,
                tags=tags, visibility=visibility,
            )
        result = await self._run_action(_do)
        if result.get("success"):
            data = result.get("data", {})
            return {"success": True, "text": f"视频发布成功: Title:{data.get('title','')} Status:{data.get('status','')}"}
        return {"success": False, "text": result.get("error", "视频发布失败")}

    # ----------------------------------------------------------
    # Feed / 搜索
    # ----------------------------------------------------------
    async def list_feeds(self) -> Dict:
        result = await self._run_action(lambda a: a.list_feeds())
        if result.get("success"):
            feeds = result.get("feeds", [])
            lines = [f"获取到 {len(feeds)} 条推荐内容：\n"]
            for i, f in enumerate(feeds[:20], 1):
                nc = f.get("note_card", {})
                title = nc.get("display_title", "无标题")
                user = nc.get("user", {}).get("nickname", "")
                likes = nc.get("interact_info", {}).get("liked_count", "0")
                lines.append(f"{i}. [{title}] by {user} | 👍{likes} | id={f.get('id','')} xsec_token={f.get('xsec_token','')}")
            return {"success": True, "text": "\n".join(lines)}
        return {"success": False, "text": result.get("error", "获取失败")}

    async def search_feeds(self, keyword: str, sort_by: str = "综合", note_type: str = "不限") -> Dict:
        async def _do(actions: XHSActions):
            return await actions.search_feeds(keyword, sort_by, note_type)
        result = await self._run_action(_do)
        if result.get("success"):
            feeds = result.get("feeds", [])
            lines = [f"搜索「{keyword}」找到 {len(feeds)} 条结果：\n"]
            for i, f in enumerate(feeds[:20], 1):
                nc = f.get("note_card", {})
                title = nc.get("display_title", "无标题")
                user = nc.get("user", {}).get("nickname", "")
                likes = nc.get("interact_info", {}).get("liked_count", "0")
                lines.append(f"{i}. [{title}] by {user} | 👍{likes} | id={f.get('id','')} xsec_token={f.get('xsec_token','')}")
            return {"success": True, "text": "\n".join(lines)}
        return {"success": False, "text": result.get("error", "搜索失败")}

    # ----------------------------------------------------------
    # 详情
    # ----------------------------------------------------------
    async def get_feed_detail(self, feed_id: str, xsec_token: str, load_all_comments: bool = False) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.get_feed_detail(feed_id, xsec_token, load_all_comments)
        result = await self._run_action(_do)
        if result.get("success"):
            d = result.get("detail", {})
            lines = [
                f"📝 {d.get('title', '')}",
                f"👤 {d.get('user', {}).get('nickname', '')}",
                f"📄 {d.get('desc', '')[:200]}",
                f"👍 {d.get('interact_info', {}).get('liked_count', '0')} "
                f"⭐ {d.get('interact_info', {}).get('collected_count', '0')} "
                f"💬 {d.get('interact_info', {}).get('comment_count', '0')}",
            ]
            comments = d.get("comments", [])
            if comments:
                lines.append(f"\n评论 ({len(comments)} 条):")
                for c in comments[:10]:
                    lines.append(f"  - {c.get('nickname','')}: {c.get('content','')}")
            return {"success": True, "text": "\n".join(lines)}
        return {"success": False, "text": result.get("error", "获取失败")}

    # ----------------------------------------------------------
    # 评论
    # ----------------------------------------------------------
    async def post_comment(self, feed_id: str, xsec_token: str, content: str) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.post_comment(feed_id, xsec_token, content)
        result = await self._run_action(_do)
        return {"success": result.get("success", False), "text": result.get("message", result.get("error", ""))}

    async def reply_comment(self, feed_id: str, xsec_token: str, content: str, comment_id: str = "", user_id: str = "") -> Dict:
        async def _do(actions: XHSActions):
            return await actions.reply_comment(feed_id, xsec_token, content, comment_id, user_id)
        result = await self._run_action(_do)
        return {"success": result.get("success", False), "text": result.get("message", result.get("error", ""))}

    # ----------------------------------------------------------
    # 点赞 / 收藏
    # ----------------------------------------------------------
    async def like_feed(self, feed_id: str, xsec_token: str, unlike: bool = False) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.like_feed(feed_id, xsec_token, unlike)
        result = await self._run_action(_do)
        return {"success": result.get("success", False), "text": result.get("message", result.get("error", ""))}

    async def favorite_feed(self, feed_id: str, xsec_token: str, unfavorite: bool = False) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.favorite_feed(feed_id, xsec_token, unfavorite)
        result = await self._run_action(_do)
        return {"success": result.get("success", False), "text": result.get("message", result.get("error", ""))}

    # ----------------------------------------------------------
    # 用户主页
    # ----------------------------------------------------------
    async def user_profile(self, user_id: str, xsec_token: str) -> Dict:
        async def _do(actions: XHSActions):
            return await actions.user_profile(user_id, xsec_token)
        result = await self._run_action(_do)
        if result.get("success"):
            p = result.get("profile", {})
            lines = [
                f"👤 {p.get('nickname', '')}",
                f"📝 {p.get('desc', '')}",
                f"关注: {p.get('follows', '0')} | 粉丝: {p.get('fans', '0')} | 获赞: {p.get('interaction', '0')}",
            ]
            notes = p.get("notes", [])
            if notes:
                lines.append(f"\n笔记 ({len(notes)} 篇):")
                for n in notes[:10]:
                    lines.append(f"  - {n.get('title','')} | 👍{n.get('liked_count','0')} | id={n.get('id','')}")
            return {"success": True, "text": "\n".join(lines)}
        return {"success": False, "text": result.get("error", "获取失败")}

    # ----------------------------------------------------------
    # 生命周期
    # ----------------------------------------------------------
    async def close(self):
        await self.browser_mgr.close()
