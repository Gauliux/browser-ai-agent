from __future__ import annotations

from typing import Any, Optional, Protocol

from agent.core.graph_state import STOP_TO_TERMINAL, TERMINAL_TYPES


class _TextLog(Protocol):
    def write(self, message: str) -> None: ...


class _Trace(Protocol):
    def write(self, record: Any) -> None: ...


def normalize_terminal(
    result: dict[str, Any],
    *,
    session_id: str,
    text_log: _TextLog,
    trace: Optional[_Trace] = None,
) -> dict[str, Any]:
    stop_reason = result.get("stop_reason")
    if not stop_reason:
        stop_reason = "goal_failed"
        result["stop_reason"] = stop_reason
        result["stop_details"] = "no_stop_condition_reached"

    terminal_reason = result.get("terminal_reason") or STOP_TO_TERMINAL.get(stop_reason) or "goal_failed"
    result["terminal_reason"] = terminal_reason
    result["terminal_type"] = TERMINAL_TYPES.get(terminal_reason, "failure")

    try:
        text_log.write(
            f"[{session_id}] finished reason={result.get('stop_reason')} terminal={result.get('terminal_type')} "
            f"stage={result.get('goal_stage')} details={result.get('stop_details')} "
            f"url={(result.get('observation').url if result.get('observation') else None)} "
            f"progress={result.get('last_progress_score')} evidence={result.get('last_progress_evidence')}"
        )
    except Exception:
        pass

    if trace:
        try:
            trace.write(
                {
                    "summary": True,
                    "session_id": session_id,
                    "stop_reason": result.get("stop_reason"),
                    "stop_details": result.get("stop_details"),
                    "terminal_reason": result.get("terminal_reason"),
                    "terminal_type": result.get("terminal_type"),
                    "goal_stage": result.get("goal_stage"),
                    "url": result.get("observation").url if result.get("observation") else None,
                    "progress": result.get("last_progress_score"),
                    "evidence": result.get("last_progress_evidence"),
                }
            )
        except Exception:
            pass

    return result

