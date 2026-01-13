Module: src/agent/legacy/loop.py
================================

Responsibility
--------------
- Legacy custom loop implementation (Observe → Planner → Security → Execute → Progress) predating LangGraph.
- Kept for fallback/debug; not under active development.

Notes
-----
- Modern flow uses LangGraph (src/agent/langgraph_loop.py). Legacy lacks newer invariants (terminals, stage-based constraints, loop mitigation improvements).
- main.py may fall back to legacy if LangGraph fails to initialize (rare).
