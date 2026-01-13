from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import Page

from agent.config.config import Settings
from agent.core.observe import Observation, capture_observation


@dataclass
class ExecutionResult:
    success: bool
    action: Dict[str, Any]
    error: Optional[str]
    screenshot_path: Optional[Path]
    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "success": self.success,
            "action": self.action,
            "error": self.error,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
        }


def save_execution_result(result: ExecutionResult, state_dir: Path, *, label: Optional[str] = None) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    timestamp_for_file = result.recorded_at.replace(":", "").replace("-", "")
    safe_label = _sanitize_label(label)
    name = f"execute-{safe_label}-{timestamp_for_file}.json" if safe_label else f"execute-{timestamp_for_file}.json"
    path = state_dir / name
    with path.open("w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    return path


async def _locate_element(page: Page, element_id: int):
    locator = page.locator(f'[data-agent-id="{element_id}"]')
    if await locator.count() == 0:
        raise RuntimeError(f"Element with data-agent-id={element_id} not found.")
    return locator.first


async def execute_action(
    page: Page,
    observation: Observation,
    action: Dict[str, Any],
    *,
    screenshots_dir: Path,
    submit_after_type: bool = False,
    screenshot_label: Optional[str] = None,
    scroll_step: int = 600,
) -> ExecutionResult:
    now = datetime.now(timezone.utc)
    recorded_at = now.isoformat()
    action_type = action.get("action")
    element_id = action.get("element_id")
    value = action.get("value")

    if action_type in {"done", "ask_user"}:
        return ExecutionResult(
            success=True,
            action=action,
            error=None,
            screenshot_path=None,
            recorded_at=recorded_at,
        )

    try:
        if action_type == "go_back":
            await page.go_back()
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-back", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)
        if action_type == "go_forward":
            await page.go_forward()
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-forward", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)
        if action_type == "navigate":
            if not value:
                raise RuntimeError("Navigate action requires a URL in 'value'.")
            await page.goto(str(value))
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-navigate", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)
        if action_type == "search":
            if not value:
                raise RuntimeError("Search action requires a query in 'value'.")
            # If element_id is provided, focus that element before typing; otherwise fallback to omnibox.
            query = str(value)
            if element_id is not None:
                locator = await _locate_element(page, int(element_id))
                await locator.scroll_into_view_if_needed()
                try:
                    await locator.click()
                except Exception:
                    pass
                await locator.fill(query)
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
            else:
                try:
                    await page.keyboard.type(query)
                    await page.keyboard.press("Enter")
                except Exception:
                    await page.keyboard.press("Control+L")
                    await page.keyboard.type(query)
                    await page.keyboard.press("Enter")
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-search", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)
        if action_type == "scroll":
            if element_id is None:
                await page.mouse.wheel(0, scroll_step)
            else:
                locator = await _locate_element(page, element_id)
                await locator.scroll_into_view_if_needed()
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-scroll", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)

        if action_type == "click":
            if element_id is None:
                raise RuntimeError("Click action requires element_id.")
            locator = await _locate_element(page, int(element_id))
            await locator.scroll_into_view_if_needed()
            await locator.click()
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-click", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)

        if action_type == "type":
            if value is None:
                raise RuntimeError("Type action requires a non-null value.")
            locator = await _locate_element(page, int(element_id))
            await locator.scroll_into_view_if_needed()
            await locator.fill(str(value))
            if submit_after_type:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
            screenshot = await _maybe_capture(page, screenshots_dir, prefix="exec-type", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)

        if action_type == "screenshot":
            screenshot = await _capture(page, screenshots_dir, prefix="exec-shot", label=screenshot_label)
            return ExecutionResult(True, action, None, screenshot, recorded_at)

        raise RuntimeError(f"Unsupported action type: {action_type}")
    except Exception as exc:
        return ExecutionResult(
            success=False,
            action=action,
            error=str(exc),
            screenshot_path=None,
            recorded_at=recorded_at,
        )


def _timestamped_path(folder: Path, prefix: str, *, label: Optional[str] = None) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if label:
        safe_label = _sanitize_label(label)
        return folder / f"{prefix}-{safe_label}-{ts}.png"
    return folder / f"{prefix}-{ts}.png"


async def _capture(page: Page, folder: Path, *, prefix: str, label: Optional[str] = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = _timestamped_path(folder, prefix, label=label)
    await page.screenshot(path=str(path), full_page=False)
    return path


async def _maybe_capture(page: Page, folder: Path, *, prefix: str, label: Optional[str] = None) -> Optional[Path]:
    try:
        return await _capture(page, folder, prefix=prefix, label=label)
    except Exception:
        return None


def _sanitize_label(label: Optional[str]) -> str:
    if not label:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", label)
    return cleaned.strip("-_")


async def _execute_js_click(page: Page, element_id: int) -> None:
    locator = page.locator(f'[data-agent-id="{element_id}"]')
    if await locator.count() == 0:
        raise RuntimeError(f"Element with data-agent-id={element_id} not found for JS click.")
    await page.evaluate("(el) => el.click()", locator)


def _text_by_element_id(observation: Observation, element_id: Optional[int]) -> str:
    if element_id is None:
        return ""
    for el in observation.mapping:
        if el.id == element_id:
            return el.text or ""
    return ""


async def _execute_by_text(page: Page, text: str) -> None:
    if not text:
        raise RuntimeError("No text provided for text-match fallback.")
    locator = page.get_by_text(text, exact=False).first
    if await locator.count() == 0:
        raise RuntimeError(f"No element found by text match: {text!r}")
    await locator.scroll_into_view_if_needed()
    await locator.click()


async def execute_with_fallbacks(
    page: Page,
    settings: Settings,
    action: Dict[str, Any],
    observation: Observation,
    *,
    max_reobserve_attempts: int = 1,
    observation_label: Optional[str] = None,
    trace: Optional[Any] = None,
    session_id: Optional[str] = None,
    step: Optional[int] = None,
) -> Tuple[ExecutionResult, Observation]:
    current_observation = observation
    label = observation_label or (f"{session_id}-step{step}" if session_id is not None and step is not None else None)

    result = await execute_action(
        page,
        current_observation,
        action,
        screenshots_dir=settings.paths.screenshots_dir,
        submit_after_type=settings.type_submit_fallback,
        screenshot_label=label,
        scroll_step=settings.scroll_step,
    )
    if result.success or action.get("action") in {"ask_user", "done"}:
        return result, current_observation

    scroll_direction = 1
    for attempt_idx in range(max_reobserve_attempts):
        if action.get("action") != "scroll":
            try:
                scroll_delta = settings.scroll_step * scroll_direction
                await page.mouse.wheel(0, scroll_delta)
                scroll_direction *= -1  # alternate direction
            except Exception:
                pass
        setattr(page, "_hide_overlay", settings.hide_overlay)
        current_observation = await capture_observation(page, settings, label=label)
        retry_result = await execute_action(
            page,
            current_observation,
            action,
            screenshots_dir=settings.paths.screenshots_dir,
            scroll_step=settings.scroll_step,
        )
        if retry_result.success:
            return retry_result, current_observation
        result = retry_result
        if trace and session_id is not None:
            try:
                trace.write(
                    {
                        "step": step,
                        "session_id": session_id,
                        "action": action,
                        "reobserve_attempt": attempt_idx + 1,
                        "scroll_direction": scroll_direction,
                        "success": retry_result.success,
                        "error": retry_result.error,
                    }
                )
            except Exception:
                pass

    if action.get("action") == "click" and action.get("element_id") is not None:
        try:
            await _execute_js_click(page, int(action["element_id"]))
            js_result = ExecutionResult(
                success=True,
                action=action,
                error=None,
                screenshot_path=await _maybe_capture(
                    page, settings.paths.screenshots_dir, prefix="exec-js-click", label=label
                ),
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )
            return js_result, current_observation
        except Exception as exc:
            result = ExecutionResult(
                success=False,
                action=action,
                error=str(exc),
                screenshot_path=None,
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )

    if action.get("action") == "click":
        text = _text_by_element_id(current_observation, action.get("element_id"))
        if text:
            try:
                await _execute_by_text(page, text)
                text_result = ExecutionResult(
                    success=True,
                    action=action,
                    error=None,
                    screenshot_path=await _maybe_capture(
                        page, settings.paths.screenshots_dir, prefix="exec-text-click", label=label
                    ),
                    recorded_at=datetime.now(timezone.utc).isoformat(),
                )
                return text_result, current_observation
            except Exception as exc:
                result = ExecutionResult(
                    success=False,
                    action=action,
                    error=str(exc),
                    screenshot_path=None,
                    recorded_at=datetime.now(timezone.utc).isoformat(),
                )

    return result, current_observation
