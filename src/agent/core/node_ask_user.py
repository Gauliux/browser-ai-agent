from __future__ import annotations

from typing import Any, Optional

from agent.core.graph_state import GraphState, INTERACTIVE_PROMPTS


def make_ask_user_node(*, trace: Optional[Any] = None) -> Any:
    async def ask_user_node(state: GraphState) -> GraphState:
        reason = state.get("stop_reason")
        details = state.get("stop_details")
        obs = state.get("observation")
        goal = state.get("goal")
        evidence = state.get("last_progress_evidence")
        url = obs.url if obs else None
        title = obs.title if obs else None
        if not INTERACTIVE_PROMPTS:
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "node": "ask_user",
                "decision": "auto_stop",
                "stop_reason": reason,
                "evidence": evidence,
                "url": url,
                "title": title,
            }
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return state
        print("\n[graph] Агент считает, что цель может быть выполнена.")
        print(f"[graph] goal={goal}")
        print(f"[graph] url={url}")
        print(f"[graph] title={title}")
        print(f"[graph] reason={reason} details={details}")
        print(f"[graph] evidence={evidence}")
        reply = input("[graph] Завершить выполнение? (y/N): ").strip().lower()
        if reply in {"y", "yes", "д", "да"}:
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "node": "ask_user",
                "decision": "confirm",
                "stop_reason": "user_confirm_done",
                "evidence": evidence,
                "url": url,
                "title": title,
            }
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return {**state, "stop_reason": "user_confirm_done"}
        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "node": "ask_user",
            "decision": "continue",
            "stop_reason": None,
            "evidence": evidence,
            "url": url,
            "title": title,
        }
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass
        return {**state, "stop_reason": None, "stop_details": None}

    return ask_user_node

