Module: src/agent/core/graph_orchestrator.py
============================================

Responsibility
--------------
- Compile a LangGraph StateGraph from prepared nodes.

Behavior
--------
- compile_graph(nodes: Dict[str, callable]) -> compiled graph.
- Fixed structure/transitions: observe → (loop_mitigation if loop_trigger else goal_check) → planner → safety → confirm → execute → progress → ask_user/error_retry/observe → END. error_retry/ask_user branches follow code; GraphRecursionError handled at the facade.

Used By
-------
- langgraph_loop.build_graph.
