Module: src/agent/infra/termination_normalizer.py
=================================================

Responsibility
--------------
- Normalize LangGraph final state into terminal_reason/type and summary record.

Behavior
--------
- normalize_terminal(state, session_id, text_log?, trace?): maps stop_reason → terminal_reason/type (budget/goal/loop), writes summary to trace/text log, stores stop_details.

Used By
-------
- langgraph_loop.run after graph execution.
