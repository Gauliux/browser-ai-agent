from __future__ import annotations

import asyncio
from typing import Any, Optional

from agent.config.config import Settings
from agent.core.graph_orchestrator import compile_graph
from agent.core.graph_state import GraphState, classify_goal_kind
from agent.core.node_ask_user import make_ask_user_node
from agent.core.node_confirm import make_confirm_node
from agent.core.node_error_retry import make_error_retry_node
from agent.core.node_execute import make_execute_node
from agent.core.node_goal_check import make_goal_check_node
from agent.core.node_loop_mitigation import make_loop_mitigation_node
from agent.core.node_observe import make_observe_node
from agent.core.node_planner import make_planner_node
from agent.core.node_progress import make_progress_node
from agent.core.node_safety import make_safety_node
from agent.infra.termination_normalizer import normalize_terminal
from agent.core.planner import Planner
from agent.infra.runtime import BrowserRuntime
from agent.infra.tracing import TextLogger, TraceLogger, generate_step_id

try:
    from langgraph.errors import GraphRecursionError  # type: ignore
except ImportError:
    GraphRecursionError = Exception  # type: ignore


class _NullLog:
    def write(self, *_: Any, **__: Any) -> None:
        return None


def _initial_state(goal: str, session_id: str, settings: Settings, runtime: BrowserRuntime) -> GraphState:
    return {
        "goal": goal,
        "goal_kind": classify_goal_kind(goal),
        "goal_stage": "orient",
        "artifact_detected": False,
        "artifact_type": None,
        "session_id": session_id,
        "step": 1,
        "repeat_count": 0,
        "stagnation_count": 0,
        "auto_scrolls_used": 0,
        "avoid_elements": [],
        "visited_urls": {},
        "visited_elements": {},
        "action_history": [],
        "records": [],
        "exec_fail_counts": {},
        "recent_observations": [],
        "conservative_probe_done": False,
        "error_retries": 0,
        "loop_mitigated": False,
        "progress_steps": 0,
        "no_progress_steps": 0,
        "planner_calls": 0,
        "tabs": [],
        "tab_events": [],
        "active_tab_id": runtime.get_active_page_id(),
        "intent_text": None,
        "intent_history": [],
        "ux_messages": [],
        "context_events": [],
    }


def build_graph(
    *,
    settings: Settings,
    planner: Planner,
    runtime: BrowserRuntime,
    execute_enabled: bool,
    text_log: Optional[TextLogger] = None,
    trace: Optional[TraceLogger] = None,
):
    text_log = text_log or _NullLog()  # type: ignore[assignment]
    nodes = {
        "observe": make_observe_node(settings=settings, runtime=runtime, trace=trace),
        "loop_mitigation": make_loop_mitigation_node(settings=settings, runtime=runtime, text_log=text_log, trace=trace),
        "goal_check": make_goal_check_node(settings=settings),
        "planner": make_planner_node(settings=settings, planner=planner, runtime=runtime, text_log=text_log, trace=trace),
        "safety": make_safety_node(trace=trace),
        "confirm": make_confirm_node(settings=settings),
        "execute": make_execute_node(settings=settings, runtime=runtime, execute_enabled=execute_enabled, text_log=text_log, trace=trace),
        "progress": make_progress_node(settings=settings, trace=trace),
        "ask_user": make_ask_user_node(trace=trace),
        "error_retry": make_error_retry_node(text_log=text_log, trace=trace),
    }
    graph = compile_graph(nodes)
    graph_config = {"recursion_limit": max(settings.max_steps + 20, 50)}

    async def run(goal: str) -> dict[str, Any]:
        session_id = generate_step_id("session")
        initial_state = _initial_state(goal, session_id, settings, runtime)
        try:
            result = await graph.ainvoke(initial_state, config=graph_config)
        except Exception as exc:
            if isinstance(exc, GraphRecursionError):
                try:
                    text_log.write(f"[{session_id}] recursion limit reached; reason={exc}")
                except Exception:
                    pass
                result = {
                    "goal": goal,
                    "session_id": session_id,
                    "stop_reason": "budget_exhausted",
                    "stop_details": f"recursion_limit; {exc}",
                    "planner_calls": 0,
                    "observation": initial_state.get("observation"),
                }
            else:
                raise
        result = normalize_terminal(result, session_id=session_id, text_log=text_log, trace=trace)
        return result

    return run
