Module: src/agent/core/graph_orchestrator.py
============================================

Responsibility
--------------
- Компилирует LangGraph StateGraph из подготовленных узлов.

Behavior
--------
- compile_graph(nodes: Dict[str, callable]) -> compiled graph.
- Фиксированная структура/переходы: observe → (loop_mitigation если loop_trigger иначе goal_check) → planner → safety → confirm → execute → progress → ask_user/error_retry/observe → END. error_retry/ask_user ветки как в коде; GraphRecursionError handled на фасаде.

Used By
-------
- langgraph_loop.build_graph.
