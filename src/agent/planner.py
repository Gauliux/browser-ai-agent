from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft7Validator
from openai import AsyncOpenAI

from agent.observe import Observation


BROWSER_ACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tool": {"type": "string", "enum": ["browser_action"]},
        "action": {
            "type": "string",
            "enum": [
                "click",
                "type",
                "scroll",
                "screenshot",
                "navigate",
                "search",
                "go_back",
                "go_forward",
                "switch_tab",
                "done",
                "ask_user",
            ],
        },
        "element_id": {"type": ["integer", "null"]},
        "value": {"type": ["string", "null"]},
        "requires_confirmation": {"type": "boolean"},
    },
    "required": ["tool", "action", "element_id", "value", "requires_confirmation"],
    "additionalProperties": False,
}

_VALIDATOR = Draft7Validator(BROWSER_ACTION_SCHEMA)


@dataclass
class PlannerResult:
    action: Dict[str, Any]
    raw_response: Dict[str, Any]
    retries_used: int
    raw_path: Optional[Path] = None


def _load_base64_image(path: Path) -> Optional[str]:
    try:
        data = path.read_bytes()
        return base64.b64encode(data).decode("ascii")
    except FileNotFoundError:
        return None
    except TypeError:
        return None


def _format_observation(observation: Observation, *, limit: int = 30) -> str:
    if not observation.mapping:
        return json.dumps({"url": observation.url, "title": observation.title, "mapping": []}, ensure_ascii=False, indent=2)

    goal_tokens: list[str] = []

    def score_mark(mark) -> int:
        score = 0
        text = (mark.text or "").lower()
        role = (mark.role or "").lower()
        tag = (mark.tag or "").lower()
        for tok in goal_tokens:
            if tok in text:
                score += 2
            elif tok in role or tok in tag:
                score += 1
        if role in {"button", "link", "a"} or tag in {"button", "a"}:
            score += 1
        if role in {"input", "textarea", "select"} or tag in {"input", "textarea", "select"}:
            score += 1
        return score

    # Balance elements across zones if zone is present.
    has_zone = any(m.zone is not None for m in observation.mapping)
    if has_zone:
        zones = {}
        for m in observation.mapping:
            z = m.zone if m.zone is not None else 0
            zones.setdefault(z, []).append(m)
        # round-robin take until limit
        selected = []
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
        mapping = selected
    else:
        mapping = observation.mapping[:limit]
    # role/goal-aware sorting within limit
    try:
        goal_tokens = _goal_tokens_from_title(observation.title)
    except Exception:
        goal_tokens = []
    mapping = sorted(mapping, key=lambda m: score_mark(m), reverse=True)
    # Slim payload to save tokens.
    payload = {
        "url": observation.url,
        "title": observation.title,
        "mapping": [
            {
                "id": m.id,
                "tag": m.tag,
                "role": m.role,
                "text": (m.text or "")[:80],
                "zone": m.zone,
                "is_fixed": m.is_fixed,
                "is_nav": m.is_nav,
            }
            for m in mapping
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _recent_context_text(observations: List[Observation]) -> str:
    parts = []
    for obs in observations[-2:]:
        parts.append(f"- {obs.recorded_at} | {obs.title} | {obs.url}")
    return "\n".join(parts) if parts else "no recent observations"


def _goal_tokens_from_title(title: str) -> list[str]:
    return [t for t in title.lower().replace(",", " ").split() if len(t) > 3]


class Planner:
    def __init__(self, api_key: str, model: str, *, base_url: Optional[str] = None) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for Planner.")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def plan(
        self,
        *,
        goal: str,
        observation: Observation,
        recent_observations: Optional[List[Observation]] = None,
        include_screenshot: bool = False,
        mapping_limit: int = 30,
        max_retries: int = 2,
        raw_log_dir: Optional[Path] = None,
        step_id: Optional[str] = None,
        loop_flag: bool = False,
        loop_exhausted: bool = False,
        avoid_elements: Optional[List[int]] = None,
        error_context: Optional[str] = None,
        progress_context: Optional[str] = None,
        actions_context: Optional[str] = None,
        listing_detected: bool = False,
        explore_mode: bool = False,
        avoid_search: bool = False,
        search_no_change: bool = False,
        page_type: Optional[str] = None,
        task_mode: Optional[str] = None,
        avoid_actions: Optional[List[str]] = None,
        candidate_elements: Optional[List[Dict[str, Any]]] = None,
        search_controls: Optional[List[int]] = None,
        state_change_hint: Optional[str] = None,
        backoff_on_rate_limit: float = 1.0,
        allowed_actions: Optional[List[str]] = None,
    ) -> PlannerResult:
        retries_used = 0
        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                action, raw = await self._plan_once(
                    goal=goal,
                    observation=observation,
                    recent_observations=recent_observations or [],
                    include_screenshot=include_screenshot,
                    mapping_limit=mapping_limit,
                    loop_flag=loop_flag,
                    loop_exhausted=loop_exhausted,
                    avoid_elements=avoid_elements,
                    error_context=error_context,
                    progress_context=progress_context,
                    actions_context=actions_context,
                    listing_detected=listing_detected,
                    explore_mode=explore_mode,
                    avoid_search=avoid_search,
                    search_no_change=search_no_change,
                    page_type=page_type,
                    task_mode=task_mode,
                    avoid_actions=avoid_actions,
                    candidate_elements=candidate_elements,
                    search_controls=search_controls,
                    state_change_hint=state_change_hint,
                    allowed_actions=allowed_actions,
                )
                _VALIDATOR.validate(action)
                raw_path = None
                if raw_log_dir:
                    raw_log_dir.mkdir(parents=True, exist_ok=True)
                    label = step_id or f"step-{attempt}"
                    raw_path = raw_log_dir / f"planner-{label}.json"
                    with raw_path.open("w", encoding="utf-8") as f:
                        json.dump(raw, f, ensure_ascii=False, indent=2)
                return PlannerResult(action=action, raw_response=raw, retries_used=retries_used, raw_path=raw_path)
            except Exception as e:
                msg = str(e).lower()
                if ("rate limit" in msg or "rate_limit" in msg) and attempt < max_retries:
                    retries_used = attempt
                    last_error = e
                    try:
                        import asyncio
                        if backoff_on_rate_limit > 0:
                            await asyncio.sleep(backoff_on_rate_limit)
                    except Exception:
                        pass
                    continue
                retries_used = attempt
                last_error = e
                continue
        raise RuntimeError(f"Planner failed after {max_retries + 1} attempts: {last_error}")

    async def _plan_once(
        self,
        *,
        goal: str,
        observation: Observation,
        recent_observations: List[Observation],
        include_screenshot: bool,
        mapping_limit: int,
        loop_flag: bool,
        loop_exhausted: bool,
        avoid_elements: Optional[List[int]],
        error_context: Optional[str],
        progress_context: Optional[str],
        actions_context: Optional[str],
        listing_detected: bool,
        explore_mode: bool,
        avoid_search: bool,
        search_no_change: bool,
        page_type: Optional[str],
        task_mode: Optional[str],
        avoid_actions: Optional[List[str]],
        candidate_elements: Optional[List[Dict[str, Any]]],
        search_controls: Optional[List[int]],
        state_change_hint: Optional[str],
        allowed_actions: Optional[List[str]],
    ) -> (Dict[str, Any], Dict[str, Any]):
        mapping_text = _format_observation(observation, limit=mapping_limit)
        recent_text = _recent_context_text(recent_observations)
        candidates_text = ""
        if candidate_elements:
            candidates_text = "\nCandidate elements (by goal tokens):\n" + json.dumps(candidate_elements[:10], ensure_ascii=False, indent=2)
        search_text = ""
        if search_controls:
            search_text = f"\nSearch controls detected (ids): {search_controls}. Use these before clicking alphabet/nav tabs."
        allowed_text = ""
        if allowed_actions:
            allowed_text = f"\nAllowed actions for current stage: {allowed_actions}. Avoid other action types."

        system_msg = (
            "You are a web-navigation planner. Decide the next browser action to achieve the goal. "
            "You may navigate by URL using action 'navigate' (value=URL) when нужно открыть сайт/домен. "
            "Use 'search' with value as query in the site search box or omnibox when goal is an open-ended search. "
            "Use 'go_back' / 'go_forward' to navigate browser history when цель требует вернуться/двигаться вперёд. "
            "Use 'switch_tab' to activate a tab by index, url, or title (value should contain a hint). "
            "Otherwise use only the provided element mapping; element_id corresponds to data-agent-id overlays. "
            "Return a single tool call that strictly matches the JSON schema."
        )

        user_text = (
            f"Goal: {goal}\n"
            f"Task mode: {task_mode or 'unknown'}\n"
            f"Current URL: {observation.url}\n"
            f"Current title: {observation.title}\n"
            f"Recent observations (latest 3):\n{recent_text}\n\n"
            f"Current mapping (top elements):\n{mapping_text}\n\n"
            f"Loop detected: {loop_flag}. Avoid previously tried elements (data-agent-id): {avoid_elements or []}.\n"
            f"Recent errors or context: {error_context or 'none'}.\n"
            f"Progress signals: {progress_context or 'none'}.\n"
            f"Loop exhausted: {loop_exhausted}. If true, prefer exploring new areas (scroll/new links) and avoid repeating the same actions.\n"
            f"Recent actions: {actions_context or 'none'}\n"
            f"Page type: {page_type or 'unknown'}; Listing detected: {listing_detected}. If listing, prefer clicking items/links, pagination, or scrolling the listing; avoid repeating search.\n"
            f"State change hint: {state_change_hint or 'none'}.\n"
            f"Explore mode: {explore_mode}. If true (goal is find/browse), rely less on search and more on browsing categories/listings.\n"
            f"Avoid search: {avoid_search}. If true, do not propose search again; pick click/scroll/navigate instead.\n"
            f"Search no change: {search_no_change}. If true, previous search did not change the page; switch strategy.\n"
            f"Avoid actions (penalize repeats on this URL): {avoid_actions or []}.\n"
            f"{candidates_text}\n"
            f"{search_text}\n"
            f"{allowed_text}\n"
            "Decide the next action. If the goal is already met, return action 'done'. "
            "If you need clarification, return action 'ask_user'. "
            "If you need to open a specific site/domain, use 'navigate' with value as URL (element_id null). "
            "If you need to search (site search or omnibox), use 'search' with value as query (element_id null unless a specific search box is mapped). "
            "Use 'go_back' / 'go_forward' to move through history when appropriate. "
            "Use 'switch_tab' with value containing index/url/title when you need another tab (element_id null). "
            "If you plan to type, include 'value'. For scrolling, set element_id to null. "
            "In find/browse tasks, follow a micro-plan: 1) find relevant section/category, 2) open listing, 3) choose a candidate by goal match, 4) act (open/add/continue). "
            "Avoid repeating the same action that had no effect; prefer a different action type when prior attempts failed. "
            "If a search bar is visible, use it before iterating alphabet tabs or header links; avoid clicking nav/alphabet tabs when a search control exists."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_text},
        ]

        if include_screenshot and observation.screenshot_path:
            encoded = _load_base64_image(observation.screenshot_path)
            if encoded:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Screenshot of current view:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{encoded}"},
                            },
                        ],
                    }
                )

        tool_def = {
            "type": "function",
            "function": {
                "name": "browser_action",
                "description": "Decide the next browser action.",
                "parameters": BROWSER_ACTION_SCHEMA,
            },
        }

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=messages,
            tools=[tool_def],
            tool_choice={"type": "function", "function": {"name": "browser_action"}},
        )

        raw = response.model_dump()
        choice = response.choices[0]
        if not choice.message.tool_calls:
            raise ValueError("Planner did not return a tool call.")

        tool_call = choice.message.tool_calls[0]
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse tool arguments: {e}") from e

        # Sanitize/patch missing required fields to avoid trivial schema errors.
        if "tool" not in args:
            args["tool"] = "browser_action"
        if "action" not in args:
            raise ValueError("Planner returned no action.")
        if "element_id" not in args:
            args["element_id"] = None
        if "value" not in args:
            args["value"] = None
        if "requires_confirmation" not in args:
            args["requires_confirmation"] = False

        return args, raw


def load_recent_observations(state_dir: Path, *, limit: int = 3) -> List[Observation]:
    if not state_dir.exists():
        return []
    files = sorted(state_dir.glob("observation-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    observations: List[Observation] = []
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            observations.append(Observation.from_dict(data))
        except Exception:
            continue
    return observations
