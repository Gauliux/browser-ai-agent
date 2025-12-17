Module: src/agent/infra/termination_normalizer.py
=================================================

Responsibility
--------------
- Нормализует итоговое состояние LangGraph в единые terminal_reason/type и summary запись.

Behavior
--------
- normalize_terminal(state, session_id, text_log?, trace?): маппит stop_reason → terminal_reason/type (budget/goal/loop), записывает summary в trace/text log, сохраняет stop_details.

Used By
-------
- langgraph_loop.run после выполнения графа.
