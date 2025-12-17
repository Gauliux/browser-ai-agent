from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.config.config import Settings
from agent.core.graph_state import GraphState, candidate_hash, extract_candidates, goal_tokens, mapping_hash
from agent.core.execute import ExecutionResult, execute_with_fallbacks, save_execution_result
from agent.infra.capture import capture_with_retry
from agent.io.ux_narration import append_ux
from agent.infra.runtime import BrowserRuntime
from agent.infra.tracing import generate_step_id


def make_execute_node(
    *,
    settings: Settings,
    runtime: BrowserRuntime,
    execute_enabled: bool,
    text_log: Any,
    trace: Optional[Any] = None,
) -> Any:
    async def execute_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        planner_result = state["planner_result"]
        if observation is None or planner_result is None:
            raise RuntimeError("Execute node missing observation or planner result")

        action = planner_result.action
        tabs_before = await runtime.get_pages_meta()
        tab_ids_before = {
            str(t.get("id") or f"idx:{t.get('index')}" or "") for t in tabs_before if (t.get("id") or t.get("index"))
        }
        context_events = list(state.get("context_events") or [])
        step_id = generate_step_id(f"{state['session_id']}-step{state.get('step', 0)}")
        exec_result_path = None
        exec_result: Optional[ExecutionResult] = None
        exec_success: Optional[bool] = None
        exec_error: Optional[str] = None
        new_obs = observation
        obs_before = observation

        def _tab_events(after_tabs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            after_ids = {str(t.get("id") or f"idx:{t.get('index')}" or "") for t in after_tabs if (t.get("id") or t.get("index"))}
            new_ids = [tid for tid in after_ids if tid and tid not in tab_ids_before]
            if not new_ids:
                return []
            new_tabs = [t for t in after_tabs if str(t.get("id") or f"idx:{t.get('index')}" or "") in new_ids]
            return [
                {
                    "type": "new_tab",
                    "tabs": new_tabs,
                    "action": action.get("action"),
                    "value": action.get("value"),
                }
            ]

        if action.get("action") == "switch_tab":
            hint_val = action.get("value")
            index_hint: Optional[int] = None
            if isinstance(hint_val, str) and hint_val.strip().isdigit():
                try:
                    index_hint = int(hint_val.strip())
                except Exception:
                    index_hint = None
            try:
                await runtime.set_active_page_by_hint(
                    url_substr=str(hint_val) if hint_val else None,
                    title_substr=str(hint_val) if hint_val else None,
                    index=index_hint,
                )
            except Exception:
                pass
            try:
                new_obs = await capture_with_retry(
                    runtime,
                    settings,
                    capture_screenshot=False,
                    label=f"{state['session_id']}-step{state.get('step', 0)}",
                )
                state["observation"] = new_obs
            except Exception:
                new_obs = observation
            exec_result = ExecutionResult(
                success=True,
                action=action,
                error=None,
                screenshot_path=None,
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )
            tabs_after = await runtime.get_pages_meta()
            active_tab_id = runtime.get_active_page_id()
            tab_events = (state.get("tab_events") or []) + _tab_events(tabs_after)
            exec_result_path = save_execution_result(
                exec_result,
                settings.paths.state_dir,
                label=f"{state['session_id']}-step{state.get('step', 0)}",
            )
            exec_success = True
            exec_error = None
            url_changed = bool(obs_before and new_obs and obs_before.url != new_obs.url)
            dom_changed = bool(mapping_hash(obs_before) != mapping_hash(new_obs)) if obs_before and new_obs else False
            state["last_state_change"] = {"url_changed": url_changed, "dom_changed": dom_changed}
            state["last_action_no_effect"] = False
            ux_messages = append_ux(
                state,
                text_log,
                f"execute: switch_tab hint={action.get('value')} url_changed={url_changed} dom_changed={dom_changed}",
            )
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": step_id,
                "action": action,
                "planner_retries": planner_result.retries_used if planner_result else 0,
                "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                "execute_success": exec_success,
                "execute_error": exec_error,
                "exec_result_path": str(exec_result_path) if exec_result_path else None,
                "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": state.get("stop_reason"),
                "stop_details": state.get("stop_details"),
                "url_changed": url_changed,
                "dom_changed": dom_changed,
                "loop_trigger_sig": state.get("loop_trigger_sig"),
                "attempts_per_element": state.get("exec_fail_counts", {}),
                "max_attempts_per_element": settings.max_attempts_per_element,
                "tabs": tabs_after,
                "active_tab_id": active_tab_id,
                "tab_events": tab_events[-3:] if tab_events else [],
                "intent": state.get("intent_text"),
                "intent_history": (state.get("intent_history") or [])[-3:],
                "ux_messages": ux_messages[-3:] if ux_messages else [],
            }
            records = state.get("records", [])
            records.append(record)
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            action_history = state.get("action_history", [])
            action_history.append(
                {
                    "action": action.get("action"),
                    "element_id": action.get("element_id"),
                    "url": new_obs.url if new_obs else None,
                    "url_changed": url_changed,
                    "dom_changed": dom_changed,
                }
            )
            visited_urls = dict(state.get("visited_urls", {}))
            if new_obs:
                visited_urls[new_obs.url] = visited_urls.get(new_obs.url, 0) + 1
            candidate_list = extract_candidates(new_obs.mapping, goal_tokens(state["goal"]), limit=10) if new_obs else state.get("candidate_elements", [])
            return {
                **state,
                "planner_result": planner_result,
                "exec_result": exec_result,
                "records": records,
                "visited_elements": state.get("visited_elements", {}),
                "visited_urls": visited_urls,
                "avoid_elements": list(state.get("avoid_elements", [])),
                "mapping_hash": mapping_hash(new_obs),
                "candidate_elements": candidate_list,
                "prev_candidate_hash": state.get("candidate_hash"),
                "candidate_hash": candidate_hash(candidate_list) if new_obs else state.get("candidate_hash"),
                "stagnation_count": 0,
                "recent_observations": (state.get("recent_observations", []) + ([new_obs] if new_obs else []))[-3:],
                "action_history": action_history,
                "observation": new_obs,
                "tabs": tabs_after,
                "active_tab_id": active_tab_id,
                "tab_events": tab_events,
                "context_events": context_events,
                "intent_text": state.get("intent_text"),
                "intent_history": state.get("intent_history"),
                "ux_messages": ux_messages,
            }

        if action.get("action") in {"done", "ask_user"}:
            if state.get("goal_stage") in {"orient", "context"}:
                records = state.get("records", [])
                record = {
                    "step": state.get("step", 0),
                    "session_id": state["session_id"],
                    "step_id": step_id,
                    "action": action,
                    "planner_retries": planner_result.retries_used if planner_result else 0,
                    "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                    "execute_success": False,
                    "execute_error": "meta_not_allowed_in_stage",
                    "exec_result_path": None,
                    "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                    "loop_trigger": state.get("loop_trigger"),
                    "stop_reason": "planner_disallowed_action",
                    "stop_details": f"action={action.get('action')}; stage={state.get('goal_stage')}",
                }
                records.append(record)
                if trace:
                    try:
                        trace.write(record)
                    except Exception:
                        pass
                return {**state, "records": records, "stop_reason": "planner_disallowed_action", "stop_details": f"action={action.get('action')}; stage={state.get('goal_stage')}"}
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": step_id,
                "action": action,
                "planner_retries": planner_result.retries_used if planner_result else 0,
                "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                "execute_success": True,
                "execute_error": None,
                "exec_result_path": None,
                "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": f"meta_{action.get('action')}",
                "stop_details": None,
            }
            records = state.get("records", [])
            records.append(record)
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "stop_reason": f"meta_{action.get('action')}",
                "stop_details": None,
                "exec_result": None,
            }

        if not execute_enabled:
            text_log.write(f"[{step_id}] execute disabled")
            exec_success = None
            exec_error = "Execution disabled"
        else:
            try:
                try:
                    exec_result, new_obs = await asyncio.wait_for(
                        execute_with_fallbacks(
                            await runtime.ensure_page(),
                            settings,
                            action,
                            observation,
                            max_reobserve_attempts=settings.max_reobserve_attempts,
                            observation_label=f"{state['session_id']}-step{state.get('step', 0)}",
                            trace=trace,
                            session_id=state["session_id"],
                            step=state.get("step", 0),
                        ),
                        timeout=settings.execute_timeout_sec,
                    )
                except Exception as exc:
                    if not runtime.is_target_closed_error(exc):
                        raise
                    text_log.write(f"[{state['session_id']}] TargetClosed detected at step={state.get('step', 0)}; retrying execute")
                    exec_result, new_obs = await asyncio.wait_for(
                        execute_with_fallbacks(
                            await runtime.ensure_page(),
                            settings,
                            action,
                            observation,
                            max_reobserve_attempts=settings.max_reobserve_attempts,
                            observation_label=f"{state['session_id']}-step{state.get('step', 0)}",
                        ),
                        timeout=settings.execute_timeout_sec,
                    )
                exec_result_path = save_execution_result(
                    exec_result,
                    settings.paths.state_dir,
                    label=f"{state['session_id']}-step{state.get('step', 0)}",
                )
                exec_success = exec_result.success
                exec_error = exec_result.error
                observation = new_obs
                state["observation"] = observation
                text_log.write(f"[{step_id}] execute {'success' if exec_success else 'failed'} action={action} err={exec_error}")
            except asyncio.TimeoutError:
                exec_success = False
                exec_error = "Execute timeout"
                text_log.write(f"[{step_id}] execute timeout; stopping")
                record = {
                    "step": state.get("step", 0),
                    "session_id": state["session_id"],
                    "step_id": step_id,
                    "action": action,
                    "planner_retries": planner_result.retries_used if planner_result else 0,
                    "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                    "execute_success": exec_success,
                    "execute_error": exec_error,
                    "exec_result_path": None,
                    "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                    "loop_trigger": state.get("loop_trigger"),
                    "stop_reason": "execute_timeout",
                    "stop_details": f"step={state.get('step', 0)}",
                    "loop_trigger_sig": state.get("loop_trigger_sig"),
                    "attempts_per_element": state.get("exec_fail_counts", {}),
                }
                records = state.get("records", [])
                records.append(record)
                if trace:
                    try:
                        trace.write(record)
                    except Exception:
                        pass
                return {**state, "records": records, "stop_reason": "execute_timeout", "stop_details": f"step={state.get('step', 0)}"}
            except Exception as exc:
                exec_success = False
                exec_error = str(exc)
                text_log.write(f"[{step_id}] execute failed: {exc}")

        visited_elements = state.get("visited_elements", {})
        visited_urls = state.get("visited_urls", {})
        avoid = set(state.get("avoid_elements", []))
        if observation:
            url = observation.url
            visited_urls[url] = visited_urls.get(url, 0) + 1
        elem_id = action.get("element_id")
        if elem_id is not None:
            key = str(elem_id)
            visited_elements[key] = visited_elements.get(key, 0) + 1
            if exec_success is False:
                avoid.add(key)
            fail_counts = state.get("exec_fail_counts", {})
            fail_counts[key] = fail_counts.get(key, 0) + 1
            if fail_counts[key] >= settings.max_attempts_per_element:
                avoid.add(key)
            state["exec_fail_counts"] = fail_counts

        url_changed = bool(obs_before and observation and obs_before.url != observation.url)
        dom_changed = bool(mapping_hash(obs_before) != mapping_hash(observation)) if obs_before and observation else False
        state["last_state_change"] = {"url_changed": url_changed, "dom_changed": dom_changed}
        state["last_action_no_effect"] = not url_changed and not dom_changed
        tabs_after = await runtime.get_pages_meta()
        active_tab_id = runtime.get_active_page_id()
        tab_events = (state.get("tab_events") or []) + _tab_events(tabs_after)
        context_events = list(state.get("context_events") or [])
        if url_changed or dom_changed or tab_events:
            reason = "redirect"
            if action.get("action") in {"navigate", "search"}:
                reason = f"action_{action.get('action')}"
            elif action.get("action") in {"go_back", "go_forward"}:
                reason = "action_history_nav"
            elif action.get("action") == "click":
                reason = "action_click"
            elif action.get("action") == "switch_tab":
                reason = "action_switch_tab"
            event = {
                "type": "context_change",
                "reason": reason,
                "before_url": obs_before.url if obs_before else None,
                "after_url": observation.url if observation else None,
                "url_changed": url_changed,
                "dom_changed": dom_changed,
                "tab_events": tab_events[-1:] if tab_events else [],
                "action": action.get("action"),
                "value": action.get("value"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            context_events.append(event)
            context_events = context_events[-10:]

        ux_messages = append_ux(
            state,
            text_log,
            f"execute: {action.get('action')} success={exec_success} url_changed={url_changed} dom_changed={dom_changed}",
        )

        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "step_id": step_id,
            "action": action,
            "planner_retries": planner_result.retries_used if planner_result else 0,
            "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
            "execute_success": exec_success,
            "execute_error": exec_error,
            "exec_result_path": str(exec_result_path) if exec_result_path else None,
            "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
            "loop_trigger": state.get("loop_trigger"),
            "stop_reason": state.get("stop_reason"),
            "stop_details": state.get("stop_details"),
            "url_changed": url_changed,
            "dom_changed": dom_changed,
            "loop_trigger_sig": state.get("loop_trigger_sig"),
            "attempts_per_element": state.get("exec_fail_counts", {}),
            "max_attempts_per_element": settings.max_attempts_per_element,
            "tabs": tabs_after,
            "active_tab_id": active_tab_id,
            "tab_events": tab_events[-3:] if tab_events else [],
            "context_events": context_events[-3:] if context_events else [],
            "intent": state.get("intent_text"),
            "intent_history": (state.get("intent_history") or [])[-3:],
            "ux_messages": ux_messages[-3:] if ux_messages else [],
        }

        records = state.get("records", [])
        records.append(record)
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass

        action_history = state.get("action_history", [])
        action_history.append(
            {
                "action": action.get("action"),
                "element_id": action.get("element_id"),
                "url": observation.url if observation else None,
                "url_changed": url_changed,
                "dom_changed": dom_changed,
            }
        )

        return {
            **state,
            "planner_result": planner_result,
            "exec_result": exec_result,
            "records": records,
            "visited_elements": visited_elements,
            "visited_urls": visited_urls,
            "avoid_elements": list(avoid),
            "last_error_context": exec_error if exec_success is False else None,
            "action_history": action_history,
            "recent_observations": list((state.get("recent_observations") or [])[-2:]) + ([observation] if observation else []),
            "tabs": tabs_after,
            "active_tab_id": active_tab_id,
            "tab_events": tab_events,
            "context_events": context_events,
            "intent_text": state.get("intent_text"),
            "intent_history": state.get("intent_history"),
            "ux_messages": ux_messages,
        }

    return execute_node
