from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

from playwright.async_api import Page

from agent.config import Settings

JS_SET_OF_MARK = r"""
({ maxElements = 30, viewports = 1, hideOverlay = false } = {}) => {
  const selectInteractive = () =>
    Array.from(
      document.querySelectorAll(
        "a,button,input,textarea,select,[role='button'],[onclick]"
      )
    );

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return false;
    const maxY = window.innerHeight * Math.max(1, viewports);
    if (rect.bottom < 0 || rect.right < 0 || rect.top > maxY || rect.left > window.innerWidth) return false;
    const style = window.getComputedStyle(el);
    return (
      style &&
      style.visibility !== "hidden" &&
      style.display !== "none" &&
      parseFloat(style.opacity || "1") > 0.05
    );
  };

  // Cleanup previous overlays
  document.querySelectorAll(".agent-overlay").forEach((n) => n.remove());

    const marks = [];
    const getEnabled = (el) => {
      const disabledAttr = el.getAttribute("disabled");
      const ariaDisabled = el.getAttribute("aria-disabled");
      return !(disabledAttr !== null || ariaDisabled === "true");
    };
  let idCounter = 1;

  for (const el of selectInteractive()) {
    if (!isVisible(el)) continue;
    const rect = el.getBoundingClientRect();
    const text = (el.innerText || el.value || "").trim().slice(0, 120);
    const role =
      el.getAttribute("role") ||
      el.getAttribute("aria-label") ||
      el.tagName.toLowerCase();
    const attrName = el.getAttribute("name") || "";
    const attrId = el.id || "";
    const ariaLabel = el.getAttribute("aria-label") || "";
    const style = window.getComputedStyle(el);
    const position = style ? style.position : "";
    const isFixed = position === "fixed" || position === "sticky";
    const navLike =
      isFixed &&
      rect.top >= 0 &&
      rect.top < Math.max(120, window.innerHeight * 0.15) &&
      rect.height < 240;

    const markId = idCounter++;
    el.setAttribute("data-agent-id", String(markId));

    if (!hideOverlay) {
      const badge = document.createElement("div");
      badge.className = "agent-overlay";
      badge.textContent = String(markId);
      Object.assign(badge.style, {
        position: "absolute",
        left: `${rect.left + window.scrollX}px`,
        top: `${rect.top + window.scrollY}px`,
        background: "rgba(0, 123, 255, 0.85)",
        color: "#fff",
        fontSize: "12px",
        fontFamily: "monospace",
        padding: "2px 4px",
        borderRadius: "4px",
        pointerEvents: "none",
        zIndex: 2147483647,
      });
      document.body.appendChild(badge);
    }

    marks.push({
      id: markId,
      tag: el.tagName.toLowerCase(),
      text,
      role,
      zone: Math.min(
        Math.max(0, Math.floor(rect.top / window.innerHeight)),
        Math.max(0, viewports - 1)
      ),
      is_fixed: isFixed,
      is_nav: navLike,
      attr_name: attrName,
      attr_id: attrId,
      aria_label: ariaLabel,
      is_disabled: !getEnabled(el),
      bbox: {
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY,
        width: rect.width,
        height: rect.height,
      },
    });

    if (marks.length >= maxElements) break;
  }

  marks.sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x);
  return marks;
}
"""


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass
class ElementMark:
    id: int
    tag: str
    text: str
    role: Optional[str]
    zone: Optional[int]
    bbox: BoundingBox
    is_fixed: bool = False
    is_nav: bool = False
    is_disabled: bool = False
    attr_name: Optional[str] = None
    attr_id: Optional[str] = None
    aria_label: Optional[str] = None

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "ElementMark":
        bbox_raw = raw.get("bbox") or {}
        return cls(
            id=int(raw["id"]),
            tag=str(raw.get("tag", "")),
            text=str(raw.get("text", "")),
            role=(raw.get("role") if raw.get("role") is not None else None),
            zone=raw.get("zone"),
            is_fixed=bool(raw.get("is_fixed", False)),
            is_nav=bool(raw.get("is_nav", False)),
            is_disabled=bool(raw.get("is_disabled", False)),
            attr_name=raw.get("attr_name"),
            attr_id=raw.get("attr_id"),
            aria_label=raw.get("aria_label"),
            bbox=BoundingBox(
                x=float(bbox_raw.get("x", 0.0)),
                y=float(bbox_raw.get("y", 0.0)),
                width=float(bbox_raw.get("width", 0.0)),
                height=float(bbox_raw.get("height", 0.0)),
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tag": self.tag,
            "text": self.text,
            "role": self.role,
            "zone": self.zone,
            "is_fixed": self.is_fixed,
            "is_nav": self.is_nav,
            "is_disabled": self.is_disabled,
            "attr_name": self.attr_name,
            "attr_id": self.attr_id,
            "aria_label": self.aria_label,
            "bbox": {
                "x": self.bbox.x,
                "y": self.bbox.y,
                "width": self.bbox.width,
                "height": self.bbox.height,
            },
        }


@dataclass
class Observation:
    url: str
    title: str
    mapping: List[ElementMark]
    screenshot_path: Optional[Path]
    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "url": self.url,
            "title": self.title,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
            "mapping": [m.to_dict() for m in self.mapping],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        mapping_raw = data.get("mapping") or []
        mapping = [ElementMark.from_raw(item) for item in mapping_raw]
        screenshot_raw = data.get("screenshot_path")
        screenshot_path = Path(screenshot_raw) if screenshot_raw else None
        return cls(
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
            mapping=mapping,
            screenshot_path=screenshot_path,
            recorded_at=str(data.get("recorded_at", "")),
        )


class ObservationRecorder:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save(self, observation: Observation, *, label: Optional[str] = None) -> Path:
        safe_label = _sanitize_label(label)
        timestamp_for_file = observation.recorded_at.replace(":", "").replace("-", "")
        name = f"observation-{safe_label}-{timestamp_for_file}.json" if safe_label else f"observation-{timestamp_for_file}.json"
        path = self.state_dir / name
        with path.open("w", encoding="utf-8") as f:
            json.dump(observation.to_dict(), f, ensure_ascii=False, indent=2)
        return path


async def collect_marks(page: Page, *, max_elements: int = 30, viewports: int = 1) -> List[ElementMark]:
    raw_marks = await page.evaluate(
        JS_SET_OF_MARK,
        {"maxElements": max_elements, "viewports": viewports, "hideOverlay": getattr(page, "_hide_overlay", False)},
    )
    return [ElementMark.from_raw(item) for item in raw_marks]


def _prioritize_mapping(mapping: List[ElementMark]) -> List[ElementMark]:
    # Push nav-like elements to the end to reduce header/footer noise; keep stable ordering by y/x otherwise.
    return sorted(
        mapping,
        key=lambda m: (
            1 if m.is_nav else 0,  # nav goes last
            0 if m.is_fixed else 1,  # fixed overlays (e.g., modal) before normal
            m.bbox.y,
            m.bbox.x,
        ),
    )


async def capture_observation(
    page: Page,
    settings: Settings,
    *,
    max_elements: Optional[int] = None,
    viewports: int = 1,
    capture_screenshot: Optional[bool] = None,
    label: Optional[str] = None,
) -> Observation:
    if settings.sync_viewport_with_window:
        try:
            size = await page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
            width = max(1, int(size.get("width", 0) or 0))
            height = max(1, int(size.get("height", 0) or 0))
            current = page.viewport_size or {}
            cur_w = int(current.get("width") or 0)
            cur_h = int(current.get("height") or 0)
            threshold = 2
            already_synced = bool(getattr(page, "_viewport_synced", False))
            if not already_synced or abs(cur_w - width) > threshold or abs(cur_h - height) > threshold:
                await page.set_viewport_size({"width": width, "height": height})
                setattr(page, "_viewport_synced", True)
        except Exception:
            pass

    effective_limit = max_elements or settings.mapping_limit
    # Adaptive mapping: boost limit when loop/stagnation is high (page attr set by caller).
    boost_limit = getattr(page, "_mapping_boost", 0)
    effective_limit = effective_limit + boost_limit

    collection_limit = effective_limit * max(1, viewports)
    mapping = await collect_marks(
        page,
        max_elements=collection_limit,
        viewports=viewports,
    )
    mapping = _prioritize_mapping(mapping)
    mapping = _apply_zone_balancing(mapping, limit=effective_limit)
    now = datetime.now(timezone.utc)
    recorded_at = now.isoformat()
    ts_label = now.strftime("%Y%m%dT%H%M%SZ")

    do_shot = capture_screenshot
    if do_shot is None:
        do_shot = settings.observe_screenshot_mode == "always"

    screenshot_path: Optional[Path] = None
    if do_shot:
        safe_label = _sanitize_label(label)
        name = f"observe-{safe_label}-{ts_label}.png" if safe_label else f"observe-{ts_label}.png"
        screenshot_path = settings.paths.screenshots_dir / name
        await page.screenshot(path=str(screenshot_path), full_page=False)

    title = await page.title()
    observation = Observation(
        url=page.url,
        title=title,
        mapping=mapping,
        screenshot_path=screenshot_path,
        recorded_at=recorded_at,
    )

    recorder = ObservationRecorder(settings.paths.state_dir)
    recorder.save(observation, label=label)

    return observation


def _sanitize_label(label: Optional[str]) -> str:
    if not label:
        return ""
    # Keep alnum, dash, underscore; replace others with dash.
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", label)
    return cleaned.strip("-_")


def _apply_zone_balancing(mapping: List[ElementMark], *, limit: int) -> List[ElementMark]:
    """Balance mapping across zones (top/mid/bottom) while keeping fixed > normal > nav priority."""
    if limit <= 0 or not mapping:
        return mapping
    zones: dict[int, List[ElementMark]] = {}
    has_zone = any(m.zone is not None for m in mapping)
    if not has_zone:
        return mapping[:limit]

    for m in mapping:
        z = m.zone if m.zone is not None else 0
        zones.setdefault(z, []).append(m)

    # Sort each zone by priority (fixed first, nav last, then by y/x)
    for z_items in zones.values():
        z_items.sort(
            key=lambda m: (
                1 if m.is_nav else 0,
                0 if m.is_fixed else 1,
                m.bbox.y,
                m.bbox.x,
            )
        )

    selected: List[ElementMark] = []
    zone_keys = sorted(zones.keys())
    while len(selected) < limit:
        progressed = False
        for z in zone_keys:
            if zones[z]:
                selected.append(zones[z].pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break

    return selected
