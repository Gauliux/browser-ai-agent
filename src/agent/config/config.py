from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agent.infra.paths import Paths

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_: object, **__: object) -> bool:
        return False


@dataclass
class Settings:
    openai_api_key: Optional[str]
    openai_model: str
    openai_base_url: Optional[str]
    start_url: str
    headless: bool
    mapping_limit: int
    planner_screenshot_mode: str
    max_steps: int
    planner_timeout_sec: float
    execute_timeout_sec: float
    auto_confirm: bool
    enable_raw_logs: bool
    loop_repeat_threshold: int
    stagnation_threshold: int
    max_auto_scrolls: int
    loop_retry_mapping_boost: int
    progress_keywords: list[str]
    auto_done_mode: str
    auto_done_threshold: int
    auto_done_require_url_change: bool
    paged_scan_steps: int
    paged_scan_viewports: int
    observe_screenshot_mode: str
    hide_overlay: bool
    viewport_width: Optional[int]
    viewport_height: Optional[int]
    sync_viewport_with_window: bool
    type_submit_fallback: bool
    conservative_observe: bool
    max_reobserve_attempts: int
    max_attempts_per_element: int
    scroll_step: int
    max_planner_calls: int
    max_no_progress_steps: int
    paths: Paths

    @classmethod
    def load(cls) -> "Settings":
        # Project root (…/agent) so .env at repo root is loaded before env vars.
        root = Path(__file__).resolve().parents[3]
        load_dotenv(root / ".env", override=True)
        paths = Paths.from_env(root)
        paths.ensure()

        def clamp_int(raw: str, *, default: int, min_value: int = 1) -> int:
            try:
                value = int(raw)
            except Exception:
                return default
            return max(min_value, value)

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        start_url = os.getenv("START_URL", "about:blank")
        headless_raw = os.getenv("HEADLESS", "false").lower()
        headless = headless_raw in {"1", "true", "yes", "on"}
        mapping_limit = clamp_int(os.getenv("MAPPING_LIMIT", "30"), default=30)
        planner_screenshot_mode = os.getenv("PLANNER_SCREENSHOT_MODE", "auto").lower()
        if planner_screenshot_mode not in {"auto", "always", "never"}:
            planner_screenshot_mode = "auto"
        max_steps = clamp_int(os.getenv("MAX_STEPS", "6"), default=6)
        try:
            planner_timeout_sec = float(os.getenv("PLANNER_TIMEOUT_SEC", "25"))
            if planner_timeout_sec <= 0:
                planner_timeout_sec = 25.0
        except Exception:
            planner_timeout_sec = 25.0
        try:
            execute_timeout_sec = float(os.getenv("EXECUTE_TIMEOUT_SEC", "20"))
            if execute_timeout_sec <= 0:
                execute_timeout_sec = 20.0
        except Exception:
            execute_timeout_sec = 20.0
        auto_confirm = os.getenv("AUTO_CONFIRM", "false").lower() in {"1", "true", "yes", "on"}
        enable_raw_logs = os.getenv("ENABLE_RAW_LOGS", "true").lower() in {"1", "true", "yes", "on"}
        loop_repeat_threshold = clamp_int(os.getenv("LOOP_REPEAT_THRESHOLD", "2"), default=2)
        stagnation_threshold = clamp_int(os.getenv("STAGNATION_THRESHOLD", "2"), default=2)
        max_auto_scrolls = clamp_int(os.getenv("MAX_AUTO_SCROLLS", "3"), default=3)
        loop_retry_mapping_boost = clamp_int(os.getenv("LOOP_RETRY_MAPPING_BOOST", "20"), default=20, min_value=0)
        progress_keywords = os.getenv(
            "PROGRESS_KEYWORDS",
            "cart,корзина,basket,checkout,add to cart,добавить в корзину,товар,product",
        ).split(",")
        progress_keywords = [kw.strip() for kw in progress_keywords if kw.strip()]
        auto_done_mode = os.getenv("AUTO_DONE_MODE", "ask").lower()
        if auto_done_mode not in {"auto", "ask"}:
            auto_done_mode = "ask"
        auto_done_threshold = clamp_int(os.getenv("AUTO_DONE_THRESHOLD", "2"), default=2)
        auto_done_require_url_change = (
            os.getenv("AUTO_DONE_REQUIRE_URL_CHANGE", "true").lower() in {"1", "true", "yes", "on"}
        )
        paged_scan_steps = clamp_int(os.getenv("PAGED_SCAN_STEPS", "2"), default=2)
        paged_scan_viewports = clamp_int(os.getenv("PAGED_SCAN_VIEWPORTS", "2"), default=2)
        observe_screenshot_mode = os.getenv("OBSERVE_SCREENSHOT_MODE", "on_demand").lower()
        if observe_screenshot_mode not in {"on_demand", "always"}:
            observe_screenshot_mode = "on_demand"
        hide_overlay = os.getenv("HIDE_OVERLAY", "false").lower() in {"1", "true", "yes", "on"}
        viewport_width = os.getenv("VIEWPORT_WIDTH")
        viewport_height = os.getenv("VIEWPORT_HEIGHT")
        viewport_width_int = int(viewport_width) if viewport_width else None
        viewport_height_int = int(viewport_height) if viewport_height else None
        sync_viewport_with_window = os.getenv("SYNC_VIEWPORT_WITH_WINDOW", "false").lower() in {"1", "true", "yes", "on"}
        type_submit_fallback = os.getenv("TYPE_SUBMIT_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}
        conservative_observe = os.getenv("CONSERVATIVE_OBSERVE", "false").lower() in {"1", "true", "yes", "on"}
        max_reobserve_attempts = clamp_int(os.getenv("MAX_REOBSERVE_ATTEMPTS", "1"), default=1)
        max_attempts_per_element = clamp_int(os.getenv("MAX_ATTEMPTS_PER_ELEMENT", "3"), default=3)
        scroll_step = clamp_int(os.getenv("SCROLL_STEP", "600"), default=600)
        max_planner_calls = clamp_int(os.getenv("MAX_PLANNER_CALLS", "20"), default=20)
        max_no_progress_steps = clamp_int(os.getenv("MAX_NO_PROGRESS_STEPS", "20"), default=20)

        return cls(
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            start_url=start_url,
            headless=headless,
            mapping_limit=mapping_limit,
            planner_screenshot_mode=planner_screenshot_mode,
            max_steps=max_steps,
            planner_timeout_sec=planner_timeout_sec,
            execute_timeout_sec=execute_timeout_sec,
            auto_confirm=auto_confirm,
            enable_raw_logs=enable_raw_logs,
            loop_repeat_threshold=loop_repeat_threshold,
            stagnation_threshold=stagnation_threshold,
            max_auto_scrolls=max_auto_scrolls,
            loop_retry_mapping_boost=loop_retry_mapping_boost,
            progress_keywords=progress_keywords,
            auto_done_mode=auto_done_mode,
            auto_done_threshold=auto_done_threshold,
            auto_done_require_url_change=auto_done_require_url_change,
            paged_scan_steps=paged_scan_steps,
            paged_scan_viewports=paged_scan_viewports,
            observe_screenshot_mode=observe_screenshot_mode,
            hide_overlay=hide_overlay,
            viewport_width=viewport_width_int,
            viewport_height=viewport_height_int,
            sync_viewport_with_window=sync_viewport_with_window,
            type_submit_fallback=type_submit_fallback,
            conservative_observe=conservative_observe,
            max_reobserve_attempts=max_reobserve_attempts,
            max_attempts_per_element=max_attempts_per_element,
            scroll_step=scroll_step,
            max_planner_calls=max_planner_calls,
            max_no_progress_steps=max_no_progress_steps,
            paths=paths,
        )
