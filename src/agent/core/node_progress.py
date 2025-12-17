from __future__ import annotations

from typing import Any, Optional

from agent.config.config import Settings
from agent.core.graph_state import (
    GraphState,
    INTERACTIVE_PROMPTS,
    goal_is_find_only,
    mapping_hash,
    page_type_from_scores,
    progress_score,
)
from agent.infra.tracing import generate_step_id


def make_progress_node(
    *,
    settings: Settings,
    trace: Optional[Any] = None,
) -> Any:
    async def progress_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        prev_observation = state.get("prev_observation")
        action = state.get("planner_result").action if state.get("planner_result") else {}
        if observation is None:
            return state

        score, evidence, url_changed, detail_confidence, mapping_goal_hits, listing_score, detail_score = progress_score(
            state["goal"],
            prev_observation,
            observation,
            action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        state_changed = url_changed or (mapping_hash(prev_observation) != mapping_hash(observation) if prev_observation else False)
        page_type = page_type_from_scores(listing_score, detail_score, detail_confidence)
        print(f"[graph] progress score={score} evidence={evidence} url_changed={url_changed} detail_confidence={detail_confidence} listing_score={listing_score} detail_score={detail_score}")
        single_hit = mapping_goal_hits >= 1 and listing_score <= 5
        if state_changed and score >= max(1, settings.auto_done_threshold) and not (page_type == "listing" and not detail_confidence and not single_hit):
            require_url = settings.auto_done_require_url_change
            mode = settings.auto_done_mode
            find_only = goal_is_find_only(state["goal"])
            list_like = listing_score > detail_score and not detail_confidence
            if state.get("goal_stage") in {"orient", "context"}:
                pass
            elif mode == "auto" and detail_confidence and (not require_url or url_changed):
                state["records"].append(
                    {
                        "step": state.get("step", 0),
                        "session_id": state["session_id"],
                        "step_id": generate_step_id(f"{state['session_id']}-progress"),
                        "action": {"action": "done", "tool": "browser_action", "element_id": None, "value": None},
                        "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                        "security_requires_confirmation": False,
                        "execute_success": True,
                        "execute_error": None,
                        "exec_result_path": None,
                        "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                        "loop_trigger": state.get("loop_trigger"),
                        "stop_reason": "progress_auto_done",
                        "stop_details": str(evidence),
                    }
                )
                if trace:
                    try:
                        trace.write(state["records"][-1])
                    except Exception:
                        pass
                    return {**state, "stop_reason": "progress_auto_done", "stop_details": str(evidence)}
            if find_only or list_like or (require_url and not url_changed) or not detail_confidence:
                if state.get("goal_stage") in {"orient", "context"}:
                    pass
                else:
                    if not INTERACTIVE_PROMPTS:
                        state["records"].append(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "step_id": generate_step_id(f"{state['session_id']}-progress"),
                                "action": {"action": "ask_user", "tool": "browser_action", "element_id": None, "value": None},
                                "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                                "security_requires_confirmation": False,
                                "execute_success": True,
                                "execute_error": None,
                                "exec_result_path": None,
                                "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                                "loop_trigger": state.get("loop_trigger"),
                                "stop_reason": "progress_ask_user",
                                "stop_details": str(evidence),
                            }
                        )
                        if trace:
                            try:
                                trace.write(state["records"][-1])
                            except Exception:
                                pass
                        return {**state, "stop_reason": "progress_ask_user", "stop_details": str(evidence)}
                    reply = input("[graph] Looks like goal may be done. Stop? (y/N): ").strip().lower()
                    if reply in {"y", "yes"}:
                        state["records"].append(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "step_id": generate_step_id(f"{state['session_id']}-progress"),
                                "action": {"action": "ask_user", "tool": "browser_action", "element_id": None, "value": None},
                                "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                                "security_requires_confirmation": False,
                                "execute_success": True,
                                "execute_error": None,
                                "exec_result_path": None,
                                "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                                "loop_trigger": state.get("loop_trigger"),
                                "stop_reason": "progress_ask_user",
                                "stop_details": str(evidence),
                            }
                        )
                        if trace:
                            try:
                                trace.write(state["records"][-1])
                            except Exception:
                                pass
                        return {**state, "stop_reason": "progress_ask_user", "stop_details": str(evidence)}

        if action.get("action") == "switch_tab":
            return {
                **state,
                "last_progress_score": score,
                "last_progress_evidence": evidence,
                "page_type": page_type,
                "no_progress_steps": state.get("no_progress_steps", 0),
                "step": state.get("step", 0) + 1,
            }

        sig = (action.get("action"), action.get("element_id"), observation.url)
        last_sig = state.get("loop_trigger_sig")
        repeat_count = state.get("repeat_count", 0)
        if sig == last_sig:
            repeat_count += 1
        else:
            repeat_count = 0
        no_prog = state.get("no_progress_steps", 0)
        if not state_changed:
            no_prog += 1
        else:
            no_prog = 0
        return {
            **state,
            "repeat_count": repeat_count,
            "loop_trigger_sig": sig,
            "last_progress_score": score,
            "last_progress_evidence": evidence,
            "step": state.get("step", 0) + 1,
            "page_type": page_type,
            "no_progress_steps": no_prog,
        }

    return progress_node
