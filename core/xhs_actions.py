"""
小红书浏览器操作 - 用 Playwright 实现所有小红书网页自动化操作
替代原 Go 项目中 xiaohongshu/ 目录下的全部 Action
"""
import json
import asyncio
import time
import base64
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from playwright.async_api import Page, TimeoutError as PWTimeout

import httpx


# ============================================================
# 数据结构
# ============================================================
@dataclass
class InteractInfo:
    liked: bool = False
    liked_count: str = "0"
    collected: bool = False
    collected_count: str = "0"
    shared_count: str = "0"
    comment_count: str = "0"


@dataclass
class User:
    user_id: str = ""
    nickname: str = ""
    avatar: str = ""


@dataclass
class NoteCard:
    type: str = ""
    display_title: str = ""
    user: User = field(default_factory=User)
    interact_info: InteractInfo = field(default_factory=InteractInfo)


@dataclass
class Feed:
    id: str = ""
    xsec_token: str = ""
    model_type: str = ""
    note_card: NoteCard = field(default_factory=NoteCard)


@dataclass
class Comment:
    id: str = ""
    user_id: str = ""
    nickname: str = ""
    content: str = ""
    like_count: str = "0"
    sub_comments: List = field(default_factory=list)


@dataclass
class FeedDetail:
    id: str = ""
    title: str = ""
    description: str = ""
    type: str = ""
    user: User = field(default_factory=User)
    interact_info: InteractInfo = field(default_factory=InteractInfo)
    tags: List[str] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)


@dataclass
class PublishResult:
    title: str = ""
    content: str = ""
    images_count: int = 0
    status: str = ""


# ============================================================
# 小红书 URL 常量
# ============================================================
XHS_EXPLORE = "https://www.xiaohongshu.com/explore"
XHS_PUBLISH = "https://creator.xiaohongshu.com/publish/publish?source=official"
XHS_CREATOR_HOME = "https://creator.xiaohongshu.com"
XHS_SEARCH = "https://www.xiaohongshu.com/search_result"
XHS_LOGIN = "https://www.xiaohongshu.com"


# ============================================================
# 核心操作类
# ============================================================
class XHSActions:
    """小红书浏览器操作集合"""

    def __init__(self, page: Page):
        self.page = page

    # ----------------------------------------------------------
    # 登录相关
    # ----------------------------------------------------------
    async def check_login_status(self) -> Dict:
        """检查登录状态"""
        try:
            await self.page.goto(XHS_EXPLORE, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # 检测是否有登录弹窗（未登录时会弹出）
            login_modal = await self.page.query_selector(".login-container")
            if login_modal:
                visible = await login_modal.is_visible()
                if visible:
                    return {"logged_in": False, "message": "未登录"}

            # 检测用户头像（已登录标志）
            avatar = await self.page.query_selector(".user .avatar-wrapper, .side-bar .user")
            if avatar:
                return {"logged_in": True, "message": "已登录", "username": "xiaohongshu-mcp"}

            # 尝试通过 cookies 判断
            cookies = await self.page.context.cookies()
            has_session = any(c["name"] in ("web_session", "a1") for c in cookies)
            if has_session:
                return {"logged_in": True, "message": "已登录", "username": "xiaohongshu-mcp"}

            return {"logged_in": False, "message": "未登录"}
        except Exception as e:
            return {"logged_in": False, "message": f"检查失败: {e}"}

    async def check_creator_login(self) -> Dict:
        """检查创作者中心（creator.xiaohongshu.com）是否已登录"""
        try:
            await self.page.goto(XHS_CREATOR_HOME, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # 如果被重定向到登录页面，说明未登录
            current_url = self.page.url
            if "login" in current_url.lower():
                return {"logged_in": False, "message": "创作者中心未登录"}

            # 检测是否有登录相关的弹窗或按钮
            login_btn = await self.page.query_selector("a[href*='login'], .login-btn, button:has-text('登录')")
            if login_btn:
                visible = await login_btn.is_visible()
                if visible:
                    return {"logged_in": False, "message": "创作者中心未登录"}

            # 检测创作者中心用户信息（已登录标志）
            user_el = await self.page.query_selector(".user-info, .creator-header .user, .dps-avatar")
            if user_el:
                return {"logged_in": True, "message": "创作者中心已登录"}

            # 通过 cookie 判断
            cookies = await self.page.context.cookies()
            creator_cookies = [c for c in cookies if "creator" in c.get("domain", "") or c.get("domain", "").endswith(".xiaohongshu.com")]
            has_session = any(c["name"] in ("web_session", "a1", "galaxy_creator_session_id") for c in creator_cookies)
            if has_session:
                return {"logged_in": True, "message": "创作者中心已登录"}

            return {"logged_in": False, "message": "创作者中心未登录"}
        except Exception as e:
            # 如果检查失败不阻塞流程，假设已登录
            return {"logged_in": True, "message": f"创作者中心检查异常(放行): {e}"}

    async def get_login_qrcode(self) -> Dict:
        """获取登录二维码"""
        try:
            await self.page.goto(XHS_LOGIN, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)

            # 等待二维码出现
            qr_el = await self.page.wait_for_selector(
                ".qrcode-img img, .login-container img[src*='qrcode']",
                timeout=15000,
            )
            if qr_el:
                src = await qr_el.get_attribute("src")
                if src and src.startswith("data:"):
                    return {"success": True, "qrcode": src, "timeout": 120}
                elif src:
                    return {"success": True, "qrcode": src, "timeout": 120}

            return {"success": False, "error": "未找到二维码"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for_login(self, timeout: int = 120) -> Dict:
        """等待扫码登录完成"""
        start = time.time()
        while time.time() - start < timeout:
            cookies = await self.page.context.cookies()
            has_session = any(c["name"] in ("web_session",) for c in cookies)
            if has_session:
                return {"success": True, "message": "登录成功"}
            await self.page.wait_for_timeout(2000)
        return {"success": False, "message": "登录超时"}

    # ----------------------------------------------------------
    # 发布相关
    # ----------------------------------------------------------
    async def publish_content(
        self,
        title: str,
        content: str,
        image_paths: List[str],
        tags: List[str] = None,
        is_original: bool = False,
        visibility: str = "公开可见",
    ) -> Dict:
        """发布图文内容到小红书"""
        try:
            # 处理图片（URL 下载为本地文件）
            local_images = await self._prepare_images(image_paths)
            if not local_images:
                return {"success": False, "error": "没有可用的图片"}

            await self.page.goto(XHS_PUBLISH, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # 1. 上传图片
            upload_input = await self.page.wait_for_selector(
                "input[type='file']", timeout=10000
            )
            await upload_input.set_input_files(local_images)
            await self.page.wait_for_timeout(5000)

            # 2. 填写标题
            title_input = await self.page.wait_for_selector(
                "#title-textarea, input.titleInput, [placeholder*='标题']",
                timeout=10000,
            )
            await title_input.click()
            await title_input.fill("")
            await title_input.type(title[:20], delay=50)  # 标题限制 20 字
            await self.page.wait_for_timeout(500)

            # 3. 填写正文
            editor = await self.page.wait_for_selector(
                "div.ql-editor, [contenteditable='true'].ql-editor, #post-textarea",
                timeout=10000,
            )
            await editor.click()
            await editor.fill("")
            # 分段输入正文
            for line in content.split("\n"):
                await self.page.keyboard.type(line, delay=20)
                await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(1000)

            # 4. 添加标签
            if tags:
                for tag in tags[:5]:  # 最多 5 个标签
                    await self.page.keyboard.type(f"#{tag}", delay=30)
                    await self.page.wait_for_timeout(800)
                    # 尝试点击标签建议
                    try:
                        tag_suggestion = await self.page.wait_for_selector(
                            ".publish-hash-tag .hash-tag-item, .suggest-item",
                            timeout=2000,
                        )
                        if tag_suggestion:
                            await tag_suggestion.click()
                    except PWTimeout:
                        await self.page.keyboard.press("Enter")
                    await self.page.wait_for_timeout(500)

            # 5. 设置可见范围（如果不是默认的公开可见）
            if visibility and visibility != "公开可见":
                await self._set_visibility(visibility)

            # 6. 原创声明
            if is_original:
                await self._set_original()

            # 7. 点击发布按钮
            await self.page.wait_for_timeout(2000)
            publish_btn = await self.page.wait_for_selector(
                "button.publishBtn, .publishBtn, button:has-text('发布')",
                timeout=10000,
            )
            await publish_btn.click()
            await self.page.wait_for_timeout(5000)

            return {
                "success": True,
                "data": asdict(PublishResult(
                    title=title,
                    content=content,
                    images_count=len(local_images),
                    status="发布完成",
                )),
            }
        except Exception as e:
            return {"success": False, "error": f"发布失败: {e}"}

    async def publish_video(
        self,
        title: str,
        content: str,
        video_path: str,
        tags: List[str] = None,
        visibility: str = "公开可见",
    ) -> Dict:
        """发布视频内容"""
        try:
            if not Path(video_path).exists():
                return {"success": False, "error": f"视频文件不存在: {video_path}"}

            await self.page.goto(XHS_PUBLISH, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # 1. 上传视频
            upload_input = await self.page.wait_for_selector(
                "input[type='file']", timeout=10000
            )
            await upload_input.set_input_files(video_path)

            # 等待视频处理（最多 3 分钟）
            await self.page.wait_for_timeout(10000)
            for _ in range(30):
                processing = await self.page.query_selector(".upload-progress, .uploading")
                if not processing:
                    break
                await self.page.wait_for_timeout(5000)

            # 2. 填写标题和正文（同图文）
            title_input = await self.page.wait_for_selector(
                "#title-textarea, input.titleInput, [placeholder*='标题']",
                timeout=10000,
            )
            await title_input.click()
            await title_input.fill("")
            await title_input.type(title[:20], delay=50)
            await self.page.wait_for_timeout(500)

            editor = await self.page.wait_for_selector(
                "div.ql-editor, [contenteditable='true']",
                timeout=10000,
            )
            await editor.click()
            await editor.fill("")
            for line in content.split("\n"):
                await self.page.keyboard.type(line, delay=20)
                await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(1000)

            # 3. 标签
            if tags:
                for tag in tags[:5]:
                    await self.page.keyboard.type(f"#{tag}", delay=30)
                    await self.page.wait_for_timeout(800)
                    try:
                        tag_suggestion = await self.page.wait_for_selector(
                            ".publish-hash-tag .hash-tag-item, .suggest-item",
                            timeout=2000,
                        )
                        if tag_suggestion:
                            await tag_suggestion.click()
                    except PWTimeout:
                        await self.page.keyboard.press("Enter")
                    await self.page.wait_for_timeout(500)

            # 4. 发布
            await self.page.wait_for_timeout(2000)
            publish_btn = await self.page.wait_for_selector(
                "button.publishBtn, .publishBtn, button:has-text('发布')",
                timeout=10000,
            )
            await publish_btn.click()
            await self.page.wait_for_timeout(5000)

            return {
                "success": True,
                "data": asdict(PublishResult(
                    title=title,
                    content=content,
                    images_count=0,
                    status="视频发布完成",
                )),
            }
        except Exception as e:
            return {"success": False, "error": f"视频发布失败: {e}"}

    # ----------------------------------------------------------
    # Feed 列表 / 搜索
    # ----------------------------------------------------------
    async def list_feeds(self) -> Dict:
        """获取首页推荐列表"""
        try:
            await self.page.goto(XHS_EXPLORE, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            feeds_data = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    if (!state || !state.feed) return JSON.stringify([]);
                    const feeds = state.feed.feeds;
                    const arr = feeds.value || feeds._value || feeds;
                    if (!Array.isArray(arr)) return JSON.stringify([]);
                    return JSON.stringify(arr.map(f => ({
                        id: f.id || '',
                        xsec_token: f.xsec_token || '',
                        model_type: f.model_type || '',
                        note_card: {
                            type: f.note_card?.type || '',
                            display_title: f.note_card?.display_title || '',
                            user: {
                                user_id: f.note_card?.user?.user_id || f.note_card?.user?.userId || '',
                                nickname: f.note_card?.user?.nickname || f.note_card?.user?.nick_name || '',
                                avatar: f.note_card?.user?.avatar || '',
                            },
                            interact_info: {
                                liked_count: f.note_card?.interact_info?.liked_count || '0',
                                collected_count: f.note_card?.interact_info?.collected_count || '0',
                                comment_count: f.note_card?.interact_info?.comment_count || '0',
                                shared_count: f.note_card?.interact_info?.shared_count || '0',
                            }
                        }
                    })));
                } catch(e) {
                    return JSON.stringify([]);
                }
            }""")

            feeds = json.loads(feeds_data) if feeds_data else []
            return {"success": True, "feeds": feeds, "count": len(feeds)}
        except Exception as e:
            return {"success": False, "error": str(e), "feeds": []}

    async def search_feeds(self, keyword: str, sort_by: str = "综合", note_type: str = "不限") -> Dict:
        """搜索小红书内容"""
        try:
            import urllib.parse
            encoded = urllib.parse.quote(keyword)
            url = f"{XHS_SEARCH}?keyword={encoded}&source=web_explore_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            # 应用筛选条件
            if sort_by != "综合":
                await self._apply_search_filter(1, sort_by)
            if note_type != "不限":
                await self._apply_search_filter(2, note_type)

            feeds_data = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    if (!state || !state.search) return JSON.stringify([]);
                    const feeds = state.search.feeds;
                    const arr = feeds.value || feeds._value || feeds;
                    if (!Array.isArray(arr)) return JSON.stringify([]);
                    return JSON.stringify(arr.map(f => ({
                        id: f.id || '',
                        xsec_token: f.xsec_token || '',
                        model_type: f.model_type || '',
                        note_card: {
                            type: f.note_card?.type || '',
                            display_title: f.note_card?.display_title || '',
                            user: {
                                user_id: f.note_card?.user?.user_id || f.note_card?.user?.userId || '',
                                nickname: f.note_card?.user?.nickname || f.note_card?.user?.nick_name || '',
                                avatar: f.note_card?.user?.avatar || '',
                            },
                            interact_info: {
                                liked_count: f.note_card?.interact_info?.liked_count || '0',
                                collected_count: f.note_card?.interact_info?.collected_count || '0',
                                comment_count: f.note_card?.interact_info?.comment_count || '0',
                                shared_count: f.note_card?.interact_info?.shared_count || '0',
                            }
                        }
                    })));
                } catch(e) {
                    return JSON.stringify([]);
                }
            }""")

            feeds = json.loads(feeds_data) if feeds_data else []
            return {"success": True, "keyword": keyword, "feeds": feeds, "count": len(feeds)}
        except Exception as e:
            return {"success": False, "error": str(e), "feeds": []}

    # ----------------------------------------------------------
    # 笔记详情
    # ----------------------------------------------------------
    async def get_feed_detail(
        self, feed_id: str, xsec_token: str, load_all_comments: bool = False
    ) -> Dict:
        """获取笔记详情"""
        try:
            url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            detail_data = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    if (!state || !state.note) return JSON.stringify(null);
                    const note = state.note.noteDetailMap;
                    const noteData = note.value || note._value || note;
                    const keys = Object.keys(noteData);
                    if (keys.length === 0) return JSON.stringify(null);
                    const detail = noteData[keys[0]];
                    const n = detail.note || detail;
                    return JSON.stringify({
                        id: n.noteId || n.id || '',
                        title: n.title || '',
                        desc: n.desc || '',
                        type: n.type || '',
                        user: {
                            user_id: n.user?.userId || '',
                            nickname: n.user?.nickname || '',
                            avatar: n.user?.avatar || '',
                        },
                        interact_info: {
                            liked: n.interactInfo?.liked || false,
                            liked_count: n.interactInfo?.likedCount || '0',
                            collected: n.interactInfo?.collected || false,
                            collected_count: n.interactInfo?.collectedCount || '0',
                            comment_count: n.interactInfo?.commentCount || '0',
                            shared_count: n.interactInfo?.shareCount || '0',
                        },
                        tags: (n.tagList || []).map(t => t.name || ''),
                        image_list: (n.imageList || []).map(img => img.urlDefault || img.url || ''),
                    });
                } catch(e) {
                    return JSON.stringify(null);
                }
            }""")

            if not detail_data or detail_data == "null":
                return {"success": False, "error": "无法获取笔记详情"}

            detail = json.loads(detail_data)

            # 加载评论
            comments = []
            if load_all_comments:
                comments = await self._load_comments()

            detail["comments"] = comments
            return {"success": True, "detail": detail}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------
    # 评论
    # ----------------------------------------------------------
    async def post_comment(self, feed_id: str, xsec_token: str, comment: str) -> Dict:
        """发表评论"""
        try:
            url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            # 找到评论输入框
            comment_input = await self.page.wait_for_selector(
                "#content-textarea, .comment-input textarea, [placeholder*='评论']",
                timeout=10000,
            )
            await comment_input.click()
            await self.page.wait_for_timeout(500)
            await self.page.keyboard.type(comment, delay=30)
            await self.page.wait_for_timeout(1000)

            # 点击提交
            submit_btn = await self.page.wait_for_selector(
                "div.bottom button.submit, button:has-text('发送')",
                timeout=5000,
            )
            await submit_btn.click()
            await self.page.wait_for_timeout(3000)

            return {"success": True, "message": "评论发布成功"}
        except Exception as e:
            return {"success": False, "error": f"评论失败: {e}"}

    async def reply_comment(
        self, feed_id: str, xsec_token: str, content: str,
        comment_id: str = "", user_id: str = "",
    ) -> Dict:
        """回复指定评论"""
        try:
            url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            # 找到目标评论并点击回复
            comment_items = await self.page.query_selector_all(".comment-item, .parent-comment")
            for item in comment_items:
                item_id = await item.get_attribute("data-id") or ""
                item_uid = await item.get_attribute("data-user-id") or ""
                if (comment_id and item_id == comment_id) or (user_id and item_uid == user_id):
                    reply_btn = await item.query_selector(".reply-btn, [class*='reply']")
                    if reply_btn:
                        await reply_btn.click()
                        await self.page.wait_for_timeout(1000)
                        break

            # 输入回复内容
            await self.page.keyboard.type(content, delay=30)
            await self.page.wait_for_timeout(500)

            submit_btn = await self.page.wait_for_selector(
                "div.bottom button.submit, button:has-text('发送')",
                timeout=5000,
            )
            await submit_btn.click()
            await self.page.wait_for_timeout(3000)

            return {"success": True, "message": "回复成功"}
        except Exception as e:
            return {"success": False, "error": f"回复失败: {e}"}

    # ----------------------------------------------------------
    # 点赞 / 收藏
    # ----------------------------------------------------------
    async def like_feed(self, feed_id: str, xsec_token: str, unlike: bool = False) -> Dict:
        """点赞/取消点赞"""
        try:
            url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            # 检查当前状态
            is_liked = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    const note = state?.note?.noteDetailMap;
                    const data = note?.value || note?._value || note;
                    const keys = Object.keys(data || {});
                    if (keys.length === 0) return false;
                    return data[keys[0]]?.note?.interactInfo?.liked || false;
                } catch(e) { return false; }
            }""")

            if (not unlike and is_liked) or (unlike and not is_liked):
                action = "取消点赞" if unlike else "点赞"
                return {"success": True, "message": f"已经是{action}状态，无需操作"}

            like_btn = await self.page.wait_for_selector(
                ".interact-container .like-wrapper, .like-lottie, span.like-icon",
                timeout=10000,
            )
            await like_btn.click()
            await self.page.wait_for_timeout(2000)

            action = "取消点赞" if unlike else "点赞"
            return {"success": True, "message": f"{action}成功"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def favorite_feed(self, feed_id: str, xsec_token: str, unfavorite: bool = False) -> Dict:
        """收藏/取消收藏"""
        try:
            url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            is_collected = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    const note = state?.note?.noteDetailMap;
                    const data = note?.value || note?._value || note;
                    const keys = Object.keys(data || {});
                    if (keys.length === 0) return false;
                    return data[keys[0]]?.note?.interactInfo?.collected || false;
                } catch(e) { return false; }
            }""")

            if (not unfavorite and is_collected) or (unfavorite and not is_collected):
                action = "取消收藏" if unfavorite else "收藏"
                return {"success": True, "message": f"已经是{action}状态，无需操作"}

            fav_btn = await self.page.wait_for_selector(
                ".interact-container .collect-icon, .collect-wrapper, span.collect-icon",
                timeout=10000,
            )
            await fav_btn.click()
            await self.page.wait_for_timeout(2000)

            action = "取消收藏" if unfavorite else "收藏"
            return {"success": True, "message": f"{action}成功"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------
    # 用户主页
    # ----------------------------------------------------------
    async def user_profile(self, user_id: str, xsec_token: str) -> Dict:
        """获取用户主页信息"""
        try:
            url = f"https://www.xiaohongshu.com/user/profile/{user_id}?xsec_token={xsec_token}&xsec_source=pc_note"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            profile_data = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    if (!state || !state.user) return JSON.stringify(null);
                    const user = state.user.userPageData;
                    const u = user.value || user._value || user;
                    return JSON.stringify({
                        user_id: u.basicInfo?.userId || '',
                        nickname: u.basicInfo?.nickname || '',
                        desc: u.basicInfo?.desc || '',
                        avatar: u.basicInfo?.imageb || u.basicInfo?.image || '',
                        gender: u.basicInfo?.gender || 0,
                        follows: u.interactions?.find(i => i.type === 'follows')?.count || '0',
                        fans: u.interactions?.find(i => i.type === 'fans')?.count || '0',
                        interaction: u.interactions?.find(i => i.type === 'interaction')?.count || '0',
                        notes: (u.notes || []).map(n => ({
                            id: n.id || n.noteId || '',
                            title: n.displayTitle || n.title || '',
                            type: n.type || '',
                            xsec_token: n.xsecToken || '',
                            liked_count: n.interactInfo?.likedCount || '0',
                        }))
                    });
                } catch(e) {
                    return JSON.stringify(null);
                }
            }""")

            if not profile_data or profile_data == "null":
                return {"success": False, "error": "无法获取用户信息"}

            return {"success": True, "profile": json.loads(profile_data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------
    async def _prepare_images(self, image_paths: List[str]) -> List[str]:
        """准备图片：URL 下载为本地文件，本地路径直接使用"""
        local_paths = []
        for path in image_paths:
            if path.startswith("http://") or path.startswith("https://"):
                local = await self._download_image(path)
                if local:
                    local_paths.append(local)
            elif Path(path).exists():
                local_paths.append(path)
        return local_paths

    async def _download_image(self, url: str) -> Optional[str]:
        """下载图片到临时目录"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                ext = ".jpg"
                ct = resp.headers.get("content-type", "")
                if "png" in ct:
                    ext = ".png"
                elif "webp" in ct:
                    ext = ".webp"
                h = hashlib.sha256(resp.content).hexdigest()[:16]
                tmp = Path(tempfile.gettempdir()) / "xiaohongshu_images"
                tmp.mkdir(exist_ok=True)
                filepath = tmp / f"{h}{ext}"
                filepath.write_bytes(resp.content)
                return str(filepath)
        except Exception:
            return None

    async def _load_comments(self) -> List[Dict]:
        """从页面加载评论列表"""
        try:
            comments_data = await self.page.evaluate("""() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    const note = state?.note?.noteDetailMap;
                    const data = note?.value || note?._value || note;
                    const keys = Object.keys(data || {});
                    if (keys.length === 0) return JSON.stringify([]);
                    const comments = data[keys[0]]?.comments || [];
                    return JSON.stringify(comments.map(c => ({
                        id: c.id || '',
                        user_id: c.userInfo?.userId || '',
                        nickname: c.userInfo?.nickname || '',
                        content: c.content || '',
                        like_count: c.likeCount || '0',
                        sub_comments: (c.subComments || []).map(s => ({
                            id: s.id || '',
                            user_id: s.userInfo?.userId || '',
                            nickname: s.userInfo?.nickname || '',
                            content: s.content || '',
                            like_count: s.likeCount || '0',
                        }))
                    })));
                } catch(e) { return JSON.stringify([]); }
            }""")
            return json.loads(comments_data) if comments_data else []
        except Exception:
            return []

    async def _apply_search_filter(self, filter_index: int, value: str):
        """应用搜索筛选条件"""
        try:
            filter_panel = await self.page.query_selector("div.filter-panel")
            if not filter_panel:
                return
            filter_group = await filter_panel.query_selector(
                f"div.filters:nth-child({filter_index})"
            )
            if not filter_group:
                return
            tags = await filter_group.query_selector_all("div.tag-item, span")
            for tag in tags:
                text = await tag.text_content()
                if text and value in text:
                    await tag.click()
                    await self.page.wait_for_timeout(2000)
                    break
        except Exception:
            pass

    async def _set_visibility(self, visibility: str):
        """设置可见范围"""
        try:
            vis_btn = await self.page.query_selector(
                ".publish-settings .visibility, [class*='visible']"
            )
            if vis_btn:
                await vis_btn.click()
                await self.page.wait_for_timeout(1000)
                options = await self.page.query_selector_all(
                    ".visibility-option, .option-item"
                )
                for opt in options:
                    text = await opt.text_content()
                    if text and visibility in text:
                        await opt.click()
                        await self.page.wait_for_timeout(500)
                        break
        except Exception:
            pass

    async def _set_original(self):
        """设置原创声明"""
        try:
            original = await self.page.query_selector(
                ".original-checkbox, input[type='checkbox'][name*='original']"
            )
            if original:
                await original.click()
                await self.page.wait_for_timeout(500)
        except Exception:
            pass
