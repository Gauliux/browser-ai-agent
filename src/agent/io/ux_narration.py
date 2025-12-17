from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Protocol

from agent.core.graph_state import GraphState


class _Log(Protocol):
    def write(self, message: str) -> None: ...


def append_ux(state: GraphState, text_log: _Log, message: str, *, keep_last: int = 30) -> List[str]:
    stamped = f"{datetime.now(timezone.utc).isoformat()} | {message}"
    try:
        text_log.write(stamped)
    except Exception:
        pass
    msgs = list(state.get("ux_messages") or [])
    msgs.append(stamped)
    return msgs[-keep_last:]

