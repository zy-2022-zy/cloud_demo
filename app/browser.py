from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import (
    Browser,
    Error as PlaywrightError,
    Page,
    async_playwright,
)


class BrowserSession:
    """A lightweight client for an existing Chromium instance exposed via CDP.

    The remote browser is not launched or closed by this application. Stopping
    Playwright only disconnects this client from the remote browser.
    """

    def __init__(self, cdp_url: str) -> None:
        self.cdp_url = cdp_url
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> Browser:
        if self._browser is not None and self._browser.is_connected():
            return self._browser

        async with self._lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser

            if self._playwright is None:
                self._playwright = await async_playwright().start()

            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self.cdp_url,
                    timeout=10_000,
                )
            except Exception:
                self._browser = None
                raise
            return self._browser

    async def disconnect(self) -> None:
        async with self._lock:
            # Do not call browser.close(): the Chromium process belongs to the
            # remote Docker service and must survive API restarts.
            self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def status(self) -> dict[str, Any]:
        browser = await self.connect()
        contexts = browser.contexts
        pages = [page for context in contexts for page in context.pages]
        return {
            "connected": browser.is_connected(),
            "browser_version": browser.version,
            "context_count": len(contexts),
            "page_count": len(pages),
        }

    async def list_pages(self) -> list[dict[str, Any]]:
        browser = await self.connect()
        result: list[dict[str, Any]] = []
        for context_index, context in enumerate(browser.contexts):
            for page_index, page in enumerate(context.pages):
                try:
                    title = await page.title()
                except PlaywrightError:
                    title = ""
                result.append(
                    {
                        "index": len(result),
                        "context_index": context_index,
                        "page_index": page_index,
                        "title": title,
                        "url": page.url,
                    }
                )
        return result

    async def get_page(self, index: int = 0) -> Page:
        browser = await self.connect()
        pages = [page for context in browser.contexts for page in context.pages]
        if not pages:
            if not browser.contexts:
                context = await browser.new_context()
            else:
                context = browser.contexts[0]
            return await context.new_page()
        if index < 0 or index >= len(pages):
            raise IndexError(f"Page index {index} does not exist; found {len(pages)} page(s)")
        return pages[index]

    async def navigate(self, url: str, page_index: int = 0) -> dict[str, str]:
        page = await self.get_page(page_index)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return {"title": await page.title(), "url": page.url}

    async def snapshot(self, page_index: int, max_chars: int) -> dict[str, str]:
        page = await self.get_page(page_index)
        try:
            text = await page.locator("body").inner_text(timeout=10_000)
        except PlaywrightError:
            text = await page.locator("html").inner_text(timeout=10_000)
        return {
            "title": await page.title(),
            "url": page.url,
            "text": text[:max_chars],
        }

    async def click(self, selector: str, page_index: int = 0) -> dict[str, str]:
        page = await self.get_page(page_index)
        await page.locator(selector).first.click(timeout=15_000)
        return {"title": await page.title(), "url": page.url}

    async def fill(
        self, selector: str, value: str, page_index: int = 0
    ) -> dict[str, str]:
        page = await self.get_page(page_index)
        await page.locator(selector).first.fill(value, timeout=15_000)
        return {"title": await page.title(), "url": page.url}
