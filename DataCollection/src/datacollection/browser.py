"""Playwright control of the slither.io page."""

from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from datacollection.game_js import INIT_SCRIPT

GAME_URL = "https://slither.io/"


class SlitherBrowser:
    """One browser page running slither.io. Use as ``async with SlitherBrowser(...) as b``."""

    def __init__(self, *, headless: bool, channel: str | None, viewport: tuple[int, int]) -> None:
        self.headless = headless
        self.channel = channel
        self.viewport = viewport
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> SlitherBrowser:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless, channel=self.channel)
        await self.open_page()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def open_page(self) -> None:
        """(Re)create the browser context and load the game."""
        if self._context:
            await self._context.close()
        assert self._browser is not None
        width, height = self.viewport
        self._context = await self._browser.new_context(viewport={"width": width, "height": height})
        await self._context.add_init_script(INIT_SCRIPT)
        self.page = await self._context.new_page()
        await self.page.goto(GAME_URL, wait_until="load")
        await self.page.wait_for_function("window.__dc && window.__dc.ready()", timeout=30_000)

    async def start_round(self, nickname: str, timeout_s: float = 45.0) -> None:
        """Click Play (or Play Again) and wait until our snake exists."""
        page = self._require_page()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            if await page.evaluate("window.__dc.inRound()"):
                return
            await page.evaluate("n => window.__dc.start(n)", nickname)
            await asyncio.sleep(0.25)
        raise TimeoutError("round did not start")

    async def read_state(self) -> dict[str, Any]:
        return await self._require_page().evaluate("window.__dc.read()")

    async def act(self, key: str | None, ms: float) -> float:
        """Hold an arrow key for ``ms`` milliseconds (runs in-page; returns immediately)."""
        return await self._require_page().evaluate("([k, ms]) => window.__dc.act(k, ms)", [key, ms])

    async def release(self) -> None:
        await self._require_page().evaluate("window.__dc.release()")

    async def screenshot_jpeg(self, quality: int) -> bytes:
        return await self._require_page().screenshot(type="jpeg", quality=quality)

    async def last_score(self, timeout_s: float = 10.0) -> str | None:
        """Text of the death screen ("Your final length was N"), once it appears."""
        page = self._require_page()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        text = None
        while loop.time() < deadline:
            text = await page.evaluate("window.__dc.lastScore()")
            if text and any(ch.isdigit() for ch in text):
                return text.strip()
            await asyncio.sleep(0.2)
        return text.strip() if text else None

    async def client_info(self) -> dict[str, Any]:
        info = await self._require_page().evaluate("window.__dc.clientInfo()")
        assert self._browser is not None
        info["browser_version"] = self._browser.version
        return info

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("browser not started")
        return self.page
