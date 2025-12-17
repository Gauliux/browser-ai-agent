from __future__ import annotations

from typing import Any, Optional

from agent.config.config import Settings
from agent.core.graph_state import GraphState
from agent.core.security import prompt_confirmation


def make_confirm_node(*, settings: Settings) -> Any:
    async def confirm_node(state: GraphState) -> GraphState:
        decision = state["security_decision"]
        planner_result = state["planner_result"]
        if not decision or not planner_result:
            raise RuntimeError("Confirm node missing data")
        allowed = prompt_confirmation(planner_result.action, decision.reason, auto_confirm=settings.auto_confirm)
        if not allowed:
            return {**state, "stop_reason": "rejected_by_user", "stop_details": decision.reason or "rejected"}
        return state

    return confirm_node
