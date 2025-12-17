from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from agent.config.config import Settings
from agent.core.graph_state import (
    GraphState,
    candidate_hash,
    extract_candidates,
    goal_tokens,
    mapping_hash,
    progress_score,
)
from agent.infra.capture import capture_with_retry
from agent.core.observe import Observation
from agent.infra.runtime import BrowserRuntime


def make_observe_node(
    *,
    settings: Settings,
    runtime: BrowserRuntime,
    trace: Optional[Any] = None,
) -> Any:
    async def observe_node(state: GraphState) -> GraphState:
        page = await runtime.ensure_page()
        setattr(page, "_hide_overlay", settings.hide_overlay)
        setattr(page, "_mapping_boost", 0)
        observation = await capture_with_retry(
            runtime,
            settings,
            capture_screenshot=False,
            label=f"{state['session_id']}-step{state.get('step', 0)}",
        )
        list_like = False
        _, _, _, detail_confidence_tmp, _, listing_score_tmp, detail_score_tmp = progress_score(
            state["goal"], state.get("prev_observation"), observation, {}, [kw.lower() for kw in settings.progress_keywords]
        )
        list_like = listing_score_tmp > detail_score_tmp and not detail_confidence_tmp
        if list_like and len(observation.mapping) < max(5, int(settings.mapping_limit * 0.5)):
            merged = list(observation.mapping)
            for _ in range(2):
                try:
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
                extra = await capture_with_retry(
                    runtime,
                    settings,
                    capture_screenshot=False,
                    label=f"{state['session_id']}-step{state.get('step', 0)}-retry",
                )
                merged.extend(extra.mapping)
            seen = set()
            unique = []
            for m in merged:
                key = (m.tag, m.text, m.role, int(m.bbox.x), int(m.bbox.y), int(m.bbox.width), int(m.bbox.height))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(m)
            observation = Observation(
                url=observation.url,
                title=observation.title,
                mapping=sorted(unique, key=lambda m: (m.bbox.y, m.bbox.x)),
                screenshot_path=observation.screenshot_path,
                recorded_at=observation.recorded_at,
            )

        repeat_count = state.get("repeat_count", 0)
        stagnation = state.get("stagnation_count", 0)
        mapping_hash_prev = state.get("mapping_hash")
        mapping_hash_curr = mapping_hash(observation)
        if mapping_hash_prev is not None and mapping_hash_prev == mapping_hash_curr:
            stagnation += 1
        else:
            stagnation = 0

        loop_detected = repeat_count >= settings.loop_repeat_threshold or stagnation >= settings.stagnation_threshold
        auto_scrolls_used = state.get("auto_scrolls_used", 0)
        recent = list(state.get("recent_observations", []))
        recent.append(observation)
        recent = recent[-3:]
        goal_tokens_list = goal_tokens(state["goal"])
        candidates = extract_candidates(observation.mapping, goal_tokens_list, limit=10)

        url_title = (observation.url + " " + observation.title).lower()
        goal_hit_url_title = any(tok in url_title for tok in goal_tokens_list if tok)
        mapping_text = " ".join((m.text or "") for m in observation.mapping).lower()
        mapping_goal_hits = sum(1 for tok in goal_tokens_list if tok in mapping_text)
        goal_satisfied = False
        evidence: List[str] = []
        goal_kind = state.get("goal_kind", "object")
        if goal_kind == "object" and goal_hit_url_title and (mapping_goal_hits >= 1 and len(observation.mapping) <= max(15, settings.mapping_limit // 2)):
            goal_satisfied = True
            evidence.append("goal_tokens_in_url_title")
            evidence.append(f"mapping_hits={mapping_goal_hits}")

        tabs_snapshot = await runtime.get_pages_meta()
        active_tab_id = runtime.get_active_page_id()

        new_state = {
            **state,
            "prev_observation": state.get("observation"),
            "observation": observation,
            "mapping_hash": mapping_hash_curr,
            "stagnation_count": stagnation,
            "auto_scrolls_used": auto_scrolls_used,
            "loop_trigger": "loop" if loop_detected else None,
            "recent_observations": recent,
            "loop_mitigated": False,
            "candidate_elements": candidates,
            "prev_candidate_hash": state.get("candidate_hash"),
            "candidate_hash": candidate_hash(candidates),
            "tabs": tabs_snapshot,
            "active_tab_id": active_tab_id,
        }
        if goal_satisfied:
            new_state["stop_reason"] = "goal_satisfied"
            new_state["stop_details"] = ";".join(evidence)
            return new_state
        return new_state

    return observe_node
