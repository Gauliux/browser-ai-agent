from __future__ import annotations

from typing import Any, Optional

from agent.core.graph_state import GraphState


def make_error_retry_node(*, text_log: Any, trace: Optional[Any] = None) -> Any:
    async def error_retry_node(state: GraphState) -> GraphState:
        retries = state.get("error_retries", 0)
        if retries >= 1:
            return state
        text_log.write(f"[{state['session_id']}] retry after error {state.get('stop_reason')}")
        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "node": "error_retry",
            "stop_reason": state.get("stop_reason"),
            "stop_details": state.get("stop_details"),
            "error_retries": retries + 1,
        }
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass
        return {
            **state,
            "stop_reason": None,
            "stop_details": None,
            "error_retries": retries + 1,
            "last_error_context": state.get("stop_reason"),
        }

    return error_retry_node

