from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.config.config import Settings
from agent.core.graph_state import GraphState, classify_task_mode, goal_is_find_only, pick_committed_action, progress_score
from agent.infra.capture import capture_with_retry
from agent.io.ux_narration import append_ux
from agent.core.planner import Planner, PlannerResult
from agent.infra.runtime import BrowserRuntime


def make_planner_node(
    *,
    settings: Settings,
    planner: Planner,
    runtime: BrowserRuntime,
    text_log: Any,
    trace: Optional[Any] = None,
) -> Any:
    async def planner_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        if observation is None:
            raise RuntimeError("Planner node missing observation")
        loop_detected = bool(state.get("loop_trigger"))
        goal_kind = state.get("goal_kind", "object")
        goal_stage = state.get("goal_stage", "orient")
        prev_observation = state.get("prev_observation")
        last_action = state.get("planner_result").action if state.get("planner_result") else (state.get("action_history", [])[-1] if state.get("action_history") else {})
        score_ctx = progress_score(
            state["goal"],
            prev_observation,
            observation,
            last_action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        (_, _, _, detail_confidence, _, listing_score, detail_score) = score_ctx
        listing_detected = listing_score > detail_score and not detail_confidence
        page_type = (
            "detail"
            if detail_confidence
            else ("listing" if listing_score > detail_score + 2 else "unknown")
        )
        explore_mode = goal_is_find_only(state["goal"]) or classify_task_mode(state["goal"]) == "find"
        mapping_limit = settings.mapping_limit + settings.loop_retry_mapping_boost if loop_detected else settings.mapping_limit
        error_context = state.get("last_error_context") or "none"
        include_screenshot = len(observation.mapping) <= max(10, int(settings.mapping_limit * 0.5))
        if error_context != "none":
            include_screenshot = True
        if include_screenshot and not observation.screenshot_path:
            observation = await capture_with_retry(
                runtime,
                settings,
                max_elements=len(observation.mapping),
                viewports=settings.paged_scan_viewports,
                capture_screenshot=True,
                label=f"{state['session_id']}-step{state.get('step', 0)}-shot",
            )
        progress_context_parts = [f"keywords={settings.progress_keywords}", f"listing_detected={listing_detected}"]
        search_no_change = False
        state_change = state.get("last_state_change") or {}
        state_change_hint = f"url={observation.url}; url_changed={state_change.get('url_changed')} dom_changed={state_change.get('dom_changed')}"
        if last_action and last_action.get("action") == "search" and not state_change.get("url_changed") and not state_change.get("dom_changed"):
            search_no_change = True
            progress_context_parts.append("search_no_change=True")
        avoid_actions: List[str] = list(state.get("avoid_actions", []))
        loop_sig = state.get("loop_trigger_sig")
        if loop_sig and loop_sig[0] == "search" and state.get("repeat_count", 0) >= 1:
            avoid_actions.append("search")
            progress_context_parts.append("avoid_search_due_to_loop=True")
        if state.get("last_action_no_effect"):
            progress_context_parts.append("last_action_no_effect=True")
        search_controls: List[int] = []
        for m in observation.mapping:
            role = (getattr(m, "role", "") or "").lower()
            tag = (getattr(m, "tag", "") or "").lower()
            txt = (getattr(m, "text", "") or "").lower()
            attr_name = (getattr(m, "attr_name", "") or "").lower() if getattr(m, "attr_name", None) else ""
            attr_id = (getattr(m, "attr_id", "") or "").lower() if getattr(m, "attr_id", None) else ""
            aria_label = (getattr(m, "aria_label", "") or "").lower() if getattr(m, "aria_label", None) else ""
            if role in {"searchbox"} or tag == "input" or tag == "textarea":
                if "search" in txt or "search" in attr_name or "search" in attr_id or "search" in aria_label:
                    search_controls.append(m.id)
        search_available = bool(search_controls)
        if listing_detected and search_available and state.get("repeat_count", 0) >= 0:
            avoid_actions.append("navigate")
            progress_context_parts.append(f"search_available={search_controls}")
        actions_context = "; ".join(
            f"{a.get('action')} el={a.get('element_id')} url_changed={a.get('url_changed')} dom_changed={a.get('dom_changed')}"
            for a in state.get("action_history", [])[-5:]
        ) or "none"
        loop_context = f"loop_trigger={state.get('loop_trigger')} auto_scrolls_used={state.get('auto_scrolls_used')} avoid={state.get('avoid_elements')} max_attempts_per_element={settings.max_attempts_per_element}"
        fail_counts = state.get("exec_fail_counts", {})
        attempts_context = f"fail_counts={fail_counts}"
        base_limit = settings.mapping_limit
        goal_len = len(state["goal"]) if state.get("goal") else 0
        dynamic_limit = base_limit + (10 if goal_len > 120 else 0) + (settings.loop_retry_mapping_boost if error_context != "none" else 0)
        mapping_limit = min(150, dynamic_limit)
        allowed_actions = ["click", "scroll", "navigate", "search", "go_back", "go_forward", "switch_tab", "type"]
        if goal_stage in {"context"}:
            allowed_actions = ["click", "scroll", "search", "go_back"]
        elif goal_stage in {"locate"}:
            allowed_actions = ["click", "type", "scroll", "search", "go_back", "navigate"]
        elif goal_stage in {"verify"}:
            allowed_actions = ["click", "scroll", "screenshot", "go_back"]
        allowed_meta = ["done", "ask_user"] if goal_stage in {"locate", "verify"} else []
        allowed_actions_meta = allowed_actions + allowed_meta
        progress_context = "; ".join(progress_context_parts + [f"allowed_actions={allowed_actions}"])
        commit_action = pick_committed_action(state.get("candidate_elements", []), observation, state)
        if commit_action:
            ux_messages = append_ux(
                state,
                text_log,
                f"plan: commit action={commit_action.get('action')} el={commit_action.get('element_id')} reason={commit_action.get('reason')}",
            )
            return {
                **state,
                "planner_result": PlannerResult(action=commit_action, raw_response={}, retries_used=0),
                "goal_stage": goal_stage,
                "terminal_reason": None,
                "ux_messages": ux_messages,
            }
        try:
            planner_result = await asyncio.wait_for(
                planner.plan(
                    goal=state["goal"],
                    observation=observation,
                    recent_observations=state.get("recent_observations", []),
                    include_screenshot=include_screenshot,
                    mapping_limit=mapping_limit,
                    max_retries=2,
                    raw_log_dir=settings.paths.state_dir if settings.enable_raw_logs else None,
                    step_id=f"{state['session_id']}-step{state.get('step', 0)}",
                    loop_flag=loop_detected,
                    loop_exhausted=loop_detected and state.get("auto_scrolls_used", 0) >= settings.max_auto_scrolls,
                    avoid_elements=state.get("avoid_elements", []),
                    error_context=error_context,
                    progress_context=progress_context,
                    actions_context=actions_context + f"; {loop_context}; {attempts_context}",
                    listing_detected=listing_detected,
                    explore_mode=explore_mode,
                    avoid_search="search" in avoid_actions,
                    search_no_change=search_no_change,
                    page_type=page_type,
                    task_mode=classify_task_mode(state["goal"]),
                    avoid_actions=avoid_actions,
                    candidate_elements=state.get("candidate_elements", []),
                    search_controls=search_controls,
                    state_change_hint=state_change_hint,
                    allowed_actions=allowed_actions,
                ),
                timeout=settings.planner_timeout_sec,
            )
            state["planner_calls"] = state.get("planner_calls", 0) + (1 + planner_result.retries_used)
            action_type = planner_result.action.get("action")
            if action_type not in allowed_actions_meta:
                state["stop_reason"] = "planner_disallowed_action"
                state["stop_details"] = f"action={action_type}; allowed={allowed_actions_meta}"
                if trace:
                    try:
                        trace.write(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "node": "planner",
                                "stop_reason": state["stop_reason"],
                                "stop_details": state["stop_details"],
                            }
                        )
                    except Exception:
                        pass
                return state
        except asyncio.TimeoutError:
            text_log.write(f"[{state['session_id']}] planner timeout at step={state.get('step', 0)}; stopping")
            records = state.get("records", [])
            planner_record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": f"{state['session_id']}-step{state.get('step', 0)}",
                "action": {"action": "planner_timeout"},
                "planner_retries": 0,
                "security_requires_confirmation": False,
                "execute_success": None,
                "execute_error": "planner timeout",
                "exec_result_path": None,
                "planner_raw_path": None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": "planner_timeout",
                "stop_details": f"step={state.get('step', 0)}",
                "loop_trigger_sig": state.get("loop_trigger_sig"),
                "attempts_per_element": state.get("exec_fail_counts", {}),
            }
            records.append(planner_record)
            if trace:
                try:
                    trace.write(planner_record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "observation": observation,
                "stop_reason": "planner_timeout",
                "stop_details": f"step={state.get('step', 0)}",
            }
        except Exception as exc:
            text_log.write(f"[{state['session_id']}] planner error at step={state.get('step', 0)}: {exc}")
            records = state.get("records", [])
            planner_record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": f"{state['session_id']}-step{state.get('step', 0)}",
                "action": {"action": "planner_error"},
                "planner_retries": 0,
                "security_requires_confirmation": False,
                "execute_success": None,
                "execute_error": str(exc),
                "exec_result_path": None,
                "planner_raw_path": None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": "planner_error",
                "stop_details": str(exc),
                "loop_trigger_sig": state.get("loop_trigger_sig"),
                "attempts_per_element": state.get("exec_fail_counts", {}),
            }
            records.append(planner_record)
            if trace:
                try:
                    trace.write(planner_record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "observation": observation,
                "stop_reason": "planner_error",
                "stop_details": str(exc),
            }
        intent_text = (
            f"step={state.get('step', 0)} intent: {planner_result.action.get('action')} "
            f"el={planner_result.action.get('element_id')} val={planner_result.action.get('value')} "
            f"reason={planner_result.action.get('reason') or 'planner_decision'} stage={goal_stage}"
        )
        intent_history = list(state.get("intent_history") or [])
        intent_history.append(
            {
                "step": state.get("step", 0),
                "action": planner_result.action.get("action"),
                "element_id": planner_result.action.get("element_id"),
                "value": planner_result.action.get("value"),
                "reason": planner_result.action.get("reason"),
                "goal_stage": goal_stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        intent_history = intent_history[-10:]
        ux_messages = append_ux(state, text_log, f"plan: {intent_text}")
        return {
            **state,
            "observation": observation,
            "planner_result": planner_result,
            "intent_text": intent_text,
            "intent_history": intent_history,
            "ux_messages": ux_messages,
        }

    return planner_node
