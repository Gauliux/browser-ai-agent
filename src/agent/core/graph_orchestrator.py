from __future__ import annotations

from typing import Any, Callable, Dict

from agent.core.graph_state import GraphState

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError("LangGraph is required for langgraph loop. Install langgraph.") from e


Node = Callable[[GraphState], Any]


def compile_graph(nodes: Dict[str, Node]) -> Any:
    workflow = StateGraph(GraphState)

    workflow.add_node("observe", nodes["observe"])
    workflow.add_node("loop_mitigation", nodes["loop_mitigation"])
    workflow.add_node("goal_check", nodes["goal_check"])
    workflow.add_node("planner", nodes["planner"])
    workflow.add_node("safety", nodes["safety"])
    workflow.add_node("confirm", nodes["confirm"])
    workflow.add_node("execute", nodes["execute"])
    workflow.add_node("progress", nodes["progress"])
    workflow.add_node("ask_user", nodes["ask_user"])
    workflow.add_node("error_retry", nodes["error_retry"])

    workflow.add_edge(START, "observe")
    workflow.add_conditional_edges(
        "observe",
        lambda state: END if state.get("stop_reason") else ("loop_mitigation" if state.get("loop_trigger") else "goal_check"),
        {"loop_mitigation": "loop_mitigation", "goal_check": "goal_check", END: END},
    )
    workflow.add_conditional_edges(
        "goal_check",
        lambda state: END if state.get("stop_reason") else "planner",
        {"planner": "planner", END: END},
    )
    workflow.add_edge("loop_mitigation", "planner")
    workflow.add_conditional_edges(
        "planner",
        lambda state: "error_retry"
        if state.get("stop_reason") in {"planner_error", "planner_timeout", "planner_disallowed_action"}
        else ("safety" if not state.get("stop_reason") else END),
        {"safety": "safety", "error_retry": "error_retry", END: END},
    )
    workflow.add_conditional_edges(
        "safety",
        lambda state: "confirm" if state["security_decision"].requires_confirmation else "execute",
        {"confirm": "confirm", "execute": "execute"},
    )
    workflow.add_conditional_edges(
        "confirm",
        lambda state: "execute" if not state.get("stop_reason") else END,
        {"execute": "execute", END: END},
    )
    workflow.add_conditional_edges(
        "execute",
        lambda state: "error_retry" if state.get("stop_reason") in {"execute_timeout", "execute_error"} else ("progress" if not state.get("stop_reason") else END),
        {"progress": "progress", "error_retry": "error_retry", END: END},
    )
    workflow.add_conditional_edges(
        "progress",
        lambda state: "ask_user" if state.get("stop_reason") == "progress_ask_user" else (END if state.get("stop_reason") else "observe"),
        {"observe": "observe", "ask_user": "ask_user", END: END},
    )
    workflow.add_conditional_edges(
        "error_retry",
        lambda state: "observe" if not state.get("stop_reason") else END,
        {"observe": "observe", END: END},
    )
    workflow.add_conditional_edges(
        "ask_user",
        lambda state: END if state.get("stop_reason") else "observe",
        {"observe": "observe", END: END},
    )

    return workflow.compile()

