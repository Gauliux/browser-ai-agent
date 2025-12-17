from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from agent.config import Settings


class BrowserRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._active_page_id: Optional[str] = None

    @property
    def page(self) -> Page:
        if not self._page or self._page.is_closed():
            raise RuntimeError("Browser page is not available. Call ensure_page() first.")
        return self._page

    @staticmethod
    def is_target_closed_error(exc: Exception) -> bool:
        """Best-effort check for closed/terminated page/context."""
        msg = str(exc).lower()
        return "target closed" in msg or "page closed" in msg or "browser has been closed" in msg

    def set_active_page(self, page: Page) -> None:
        if page.is_closed():
            return
        self._page = page
        try:
            self._active_page_id = page.guid  # type: ignore[attr-defined]
        except Exception:
            self._active_page_id = None

    def _select_alive_page(self) -> Optional[Page]:
        if not self._context:
            return None
        for p in reversed(self._context.pages):
            if not p.is_closed():
                return p
        return None

    def _handle_page_close(self, page: Page) -> None:
        if self._page and self._page == page:
            alive = self._select_alive_page()
            if alive:
                self._page = alive
                self._active_page_id = getattr(alive, "guid", None)  # type: ignore[attr-defined]
                try:
                    print(f"[runtime] Active page closed; switched to last alive page url={self._page.url}")
                except Exception:
                    print("[runtime] Active page closed; switched to last alive page")
            else:
                self._page = None
                self._active_page_id = None
                print("[runtime] Active page closed; no alive pages left")

    def _handle_new_page(self, page: Page) -> None:
        try:
            page.on("close", lambda _: self._handle_page_close(page))
        except Exception:
            pass
        self.set_active_page(page)
        print(f"[runtime] New page detected: {page.url}")

    async def get_pages_meta(self) -> list[dict[str, str]]:
        pages = []
        if not self._context:
            return pages
        for idx, p in enumerate(self._context.pages):
            try:
                pages.append(
                    {
                        "index": str(idx),
                        "id": getattr(p, "guid", None),  # type: ignore[attr-defined]
                        "url": p.url,
                        "title": await p.title(),
                        "is_closed": str(p.is_closed()),
                        "active": str(self._page == p),
                    }
                )
            except Exception:
                continue
        return pages

    def get_active_page_id(self) -> Optional[str]:
        return self._active_page_id

    def get_tab_ids(self) -> list[str]:
        """Return best-effort list of alive tab ids (guids if available)."""
        ids: list[str] = []
        if not self._context:
            return ids
        for p in self._context.pages:
            if p.is_closed():
                continue
            guid = getattr(p, "guid", None)  # type: ignore[attr-defined]
            if guid:
                ids.append(str(guid))
            else:
                # fallback to object id string to at least have a stable placeholder
                ids.append(str(id(p)))
        return ids

    async def set_active_page_by_hint(self, *, url_substr: str | None = None, title_substr: str | None = None, index: int | None = None) -> Optional[Page]:
        if not self._context:
            return None
        candidates: list[Page] = []
        for idx, p in enumerate(self._context.pages):
            if p.is_closed():
                continue
            if index is not None and idx == index:
                candidates.append(p)
                continue
            if url_substr and url_substr.lower() in (p.url or "").lower():
                candidates.append(p)
                continue
            if title_substr:
                try:
                    title = await p.title()
                    if title_substr.lower() in title.lower():
                        candidates.append(p)
                except Exception:
                    continue
        if candidates:
            self.set_active_page(candidates[-1])
            return self._page
        return None

    async def launch(self) -> Page:
        if self._context:
            return self.page

        self._playwright = await async_playwright().start()
        chromium = self._playwright.chromium
        viewport = None
        if self.settings.viewport_width and self.settings.viewport_height:
            viewport = {"width": self.settings.viewport_width, "height": self.settings.viewport_height}
        self._context = await chromium.launch_persistent_context(
            user_data_dir=str(self.settings.paths.user_data_dir),
            headless=self.settings.headless,
            viewport=viewport,
            args=["--start-maximized"],
        )

        try:
            self._context.on("page", self._handle_new_page)
        except Exception:
            pass

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        try:
            page_ref = self._page
            self._page.on("close", lambda *_: self._handle_page_close(page_ref))  # type: ignore[arg-type]
        except Exception:
            pass
        self.set_active_page(self._page)
        if self.settings.start_url:
            await self._page.goto(self.settings.start_url)
        return self._page

    async def ensure_page(self) -> Page:
        if self._page and not self._page.is_closed():
            return self._page
        if self._context:
            alive = self._select_alive_page()
            if alive:
                self.set_active_page(alive)
                return self._page  # type: ignore[return-value]
            self._page = await self._context.new_page()
            self.set_active_page(self._page)
            return self._page
        # If context missing, relaunch
        return await self.launch()

    async def close(self) -> None:
        # Gracefully close, suppressing errors if browser already terminated by user.
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        finally:
            self._context = None
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
        self._page = None

    async def idle(self) -> None:
        # Keep the process alive so the headful browser stays open until interrupted.
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
