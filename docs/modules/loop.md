Module: src/agent/legacy/loop.py
================================

Responsibility
--------------
- Legacy custom loop implementation (Observe → Planner → Security → Execute → Progress) до LangGraph.
- Сохранён для fallback/debug; не развивается.

Notes
-----
- Современный поток использует LangGraph (src/agent/langgraph_loop.py). Legacy лишён новых инвариантов (терминалы, stage-based ограничения, loop mitigation улучшений).
- main.py может откатиться к legacy если LangGraph не инициализируется (редко).
