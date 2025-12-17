from __future__ import annotations

from typing import Any, Optional

from agent.core.graph_state import GraphState
from agent.core.security import SecurityDecision, analyze_action


def make_safety_node(*, trace: Optional[Any] = None) -> Any:
    async def safety_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        planner_result = state["planner_result"]
        if observation is None or planner_result is None:
            raise RuntimeError("Safety node missing observation or planner result")
        decision = analyze_action(planner_result.action, observation)
        return {**state, "security_decision": decision}

    return safety_node
