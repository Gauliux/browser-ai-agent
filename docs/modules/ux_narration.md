Module: src/agent/io/ux_narration.py
====================================

Responsibility
--------------
- Maintain UX narration (readable messages to the user) without affecting graph logic.

API
---
- append_ux(state: GraphState, text_log, message, keep_last=30) -> List[str]: appends message to ux_messages, trims to keep_last, writes to text_log if present.

Used By
-------
- node_planner/node_execute to log intentions/results; UX layer is passive (does not influence decisions).
