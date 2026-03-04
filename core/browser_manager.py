"""
浏览器管理器 - 使用 Playwright 管理 Chromium 浏览器实例
替代原 Go 项目中的 go-rod 浏览器自动化
"""
import json
import os
import asyncio
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


COOKIES_FILE = Path(__file__).parent.parent / "cookies" / "cookies.json"


class BrowserManager:
    """浏览器管理器（单例）"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """确保浏览器实例已启动"""
        if self._browser and self._browser.is_connected():
            return

        self._playwright = await async_playwright().start()

        proxy = os.environ.get("XHS_PROXY")
        launch_opts = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if proxy:
            launch_opts["proxy"] = {"server": proxy}

        self._browser = await self._playwright.chromium.launch(**launch_opts)

        # 创建带 cookies 的上下文
        context_opts = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # 加载已保存的 cookies
        cookies = self._load_cookies()
        self._context = await self._browser.new_context(**context_opts)
        if cookies:
            await self._context.add_cookies(cookies)

    async def new_page(self) -> Page:
        """创建新页面"""
        async with self._lock:
            await self._ensure_browser()
        page = await self._context.new_page()
        # 注入反检测脚本
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return page

    async def save_cookies(self):
        """保存当前 cookies 到文件"""
        if not self._context:
            return
        cookies = await self._context.cookies()
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

    def _load_cookies(self) -> list:
        """从文件加载 cookies"""
        # 优先级: 环境变量 > 默认路径
        cookie_path = os.environ.get("COOKIES_PATH", str(COOKIES_FILE))
        p = Path(cookie_path)
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 兼容 go-rod 格式的 cookies（字段名转换）
            cookies = []
            for c in raw:
                cookie = {
                    "name": c.get("name", c.get("Name", "")),
                    "value": c.get("value", c.get("Value", "")),
                    "domain": c.get("domain", c.get("Domain", "")),
                    "path": c.get("path", c.get("Path", "/")),
                }
                if "expires" in c:
                    cookie["expires"] = c["expires"]
                elif "Expires" in c:
                    cookie["expires"] = c["Expires"]
                if c.get("secure") or c.get("Secure"):
                    cookie["secure"] = True
                if c.get("httpOnly") or c.get("HttpOnly"):
                    cookie["httpOnly"] = True
                if c.get("sameSite") or c.get("SameSite"):
                    val = c.get("sameSite", c.get("SameSite", "Lax"))
                    cookie["sameSite"] = val
                cookies.append(cookie)
            return cookies
        except Exception:
            return []

    def delete_cookies(self):
        """删除 cookies 文件"""
        cookie_path = os.environ.get("COOKIES_PATH", str(COOKIES_FILE))
        p = Path(cookie_path)
        if p.exists():
            p.unlink()

    async def close(self):
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
