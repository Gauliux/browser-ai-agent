from __future__ import annotations

import asyncio
from typing import Optional

from agent.config.config import Settings
from agent.core.observe import Observation, capture_observation
from agent.infra.runtime import BrowserRuntime


async def capture_with_retry(
    runtime: BrowserRuntime,
    settings: Settings,
    *,
    viewports: int = 1,
    label: Optional[str] = None,
    capture_screenshot: Optional[bool] = None,
    max_elements: Optional[int] = None,
) -> Observation:
    page = await runtime.ensure_page()
    try:
        setattr(page, "_hide_overlay", settings.hide_overlay)
        return await capture_observation(
            page,
            settings,
            viewports=viewports,
            label=label,
            capture_screenshot=capture_screenshot,
            max_elements=max_elements,
        )
    except Exception as exc:
        msg = str(exc).lower()
        if not (
            runtime.is_target_closed_error(exc)
            or "execution context was destroyed" in msg
            or "context was destroyed" in msg
            or "frame was detached" in msg
        ):
            raise
        page = await runtime.ensure_page()
        try:
            await asyncio.sleep(0.2)
        except Exception:
            pass
        setattr(page, "_hide_overlay", settings.hide_overlay)
        return await capture_observation(
            page,
            settings,
            viewports=viewports,
            label=label,
            capture_screenshot=capture_screenshot,
            max_elements=max_elements,
        )


async def paged_scan(runtime: BrowserRuntime, settings: Settings, *, label_prefix: Optional[str] = None) -> Observation:
    combined_mapping: list = []
    last_obs: Optional[Observation] = None
    steps = max(1, settings.paged_scan_steps)
    viewports = max(1, settings.paged_scan_viewports)
    for i in range(steps):
        obs = await capture_with_retry(
            runtime,
            settings,
            viewports=viewports,
            label=f"{label_prefix}-scan{i}" if label_prefix else None,
        )
        combined_mapping.extend(obs.mapping)
        last_obs = obs
        if i < steps - 1:
            try:
                page = await runtime.ensure_page()
                await page.mouse.wheel(0, 350)
            except Exception:
                pass

    if not last_obs:
        return await capture_with_retry(
            runtime,
            settings,
            viewports=viewports,
            label=label_prefix,
        )

    seen = set()
    deduped = []
    for m in combined_mapping:
        key = (m.tag, m.text, m.role, int(m.bbox.x), int(m.bbox.y), int(m.bbox.width), int(m.bbox.height))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    return Observation(
        url=last_obs.url,
        title=last_obs.title,
        mapping=sorted(deduped, key=lambda m: (m.bbox.y, m.bbox.x)),
        screenshot_path=last_obs.screenshot_path,
        recorded_at=last_obs.recorded_at,
    )
