from __future__ import annotations

from typing import Any, Optional

from agent.config.config import Settings
from agent.core.graph_state import GraphState, candidate_hash, extract_candidates, goal_tokens, mapping_hash
from agent.infra.capture import capture_with_retry, paged_scan
from agent.infra.runtime import BrowserRuntime


def make_loop_mitigation_node(
    *,
    settings: Settings,
    runtime: BrowserRuntime,
    text_log: Any,
    trace: Optional[Any] = None,
) -> Any:
    async def loop_mitigation_node(state: GraphState) -> GraphState:
        if not state.get("loop_trigger"):
            return state
        page = await runtime.ensure_page()
        setattr(page, "_mapping_boost", settings.loop_retry_mapping_boost)
        auto_scrolls_used = state.get("auto_scrolls_used", 0)
        conservative_done = state.get("conservative_probe_done", False)
        if settings.conservative_observe and not conservative_done:
            text_log.write(f"[{state['session_id']}] loop mitigation: conservative observe before scroll")
            if trace:
                try:
                    trace.write(
                        {
                            "step": state.get("step", 0),
                            "session_id": state["session_id"],
                            "node": "loop_mitigation",
                            "action": "conservative_pass",
                            "loop_trigger": state.get("loop_trigger"),
                        }
                    )
                except Exception:
                    pass
            observation = await capture_with_retry(
                runtime,
                settings,
                capture_screenshot=False,
                label=f"{state['session_id']}-conservative-{state.get('step', 0)}",
            )
            recent = list(state.get("recent_observations", []))
            recent.append(observation)
            recent = recent[-3:]
            goal_tokens_list = goal_tokens(state["goal"])
            candidates = extract_candidates(observation.mapping, goal_tokens_list, limit=10)
            return {
                **state,
                "conservative_probe_done": True,
                "observation": observation,
                "prev_observation": state.get("observation"),
                "mapping_hash": mapping_hash(observation),
                "stagnation_count": 0,
                "recent_observations": recent,
                "candidate_elements": candidates,
                "prev_candidate_hash": state.get("candidate_hash"),
                "candidate_hash": candidate_hash(candidates),
            }
        if auto_scrolls_used < settings.max_auto_scrolls:
            text_log.write(f"[{state['session_id']}] loop mitigation: paged scan")
            observation = await paged_scan(runtime, settings, label_prefix=state["session_id"])
            recent = list(state.get("recent_observations", []))
            recent.append(observation)
            recent = recent[-3:]
            return {
                **state,
                "observation": observation,
                "prev_observation": state.get("observation"),
                "mapping_hash": mapping_hash(observation),
                "auto_scrolls_used": auto_scrolls_used + 1,
                "stagnation_count": 0,
                "loop_mitigated": True,
                "recent_observations": recent,
            }
        if trace:
            try:
                trace.write(
                    {
                        "step": state.get("step", 0),
                        "session_id": state["session_id"],
                        "node": "loop_mitigation",
                        "action": "paged_scan_limit_reached",
                        "loop_trigger": state.get("loop_trigger"),
                    }
                )
            except Exception:
                pass
        return {**state, "loop_mitigated": True}

    return loop_mitigation_node
