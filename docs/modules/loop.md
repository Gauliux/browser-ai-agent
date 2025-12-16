Module: src/agent/loop.py (legacy)
===================================

Responsibility
--------------
- Legacy custom loop implementation (Observe → Planner → Security → Execute → Progress) prior to LangGraph adoption.
- Retained for fallback/debugging; not actively developed.

Notes
-----
- Modern flow uses LangGraph (src/agent/langgraph_loop.py). Legacy loop lacks newer safeguards (terminals invariant, stage-based allowed actions, improved loop handling).
- main.py may fallback to legacy loop if LangGraph init fails or when ui_shell runner cannot build LangGraph (rare).
