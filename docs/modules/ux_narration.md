Module: src/agent/io/ux_narration.py
====================================

Responsibility
--------------
- Поддерживать UX-нарратив (читаемые сообщения пользователю) без влияния на логику графа.

API
---
- append_ux(state: GraphState, text_log, message, keep_last=30) -> List[str]: добавляет сообщение в ux_messages, обрезает до keep_last, пишет в text_log (если есть).

Used By
-------
- node_planner/node_execute для фиксации намерений/результатов; UX слой пассивен (не влияет на решения).
