Architecture Overview
=====================

Goal
----
Headful, persistent Playwright agent orchestrated by LangGraph: observes DOM (Set-of-Mark), plans via OpenAI function-calling, executes with fallbacks and safety, tracks tabs/context events/intent/UX narration.

Key Decisions
-------------
- Stack: Python 3, Playwright headful persistent, OpenAI SDK (function-calling), LangGraph.
- Observation-first: Set-of-Mark instead of CV; element limit/balancing; screenshots on demand.
- Orchestration: fixed graph of nodes observe → loop_mitigation → goal_check → planner → safety → confirm → execute → progress → ask_user/error_retry.
- Safety: heuristics for risky actions + confirm (auto_confirm optional).
- Stable FSM/terminals: stages orient/context/locate/verify/done; terminal_reason fixed (goal_satisfied/goal_failed/loop_stuck/budget_exhausted).
- Transparency: intent_text/history, UX narration, trace.jsonl, records.

Main Components
---------------
- Runtime ([docs/modules/runtime.md](/docs/modules/runtime.md)): browser lifecycle, active tab tracking, TargetClosed resilience, tab metadata.
- Capture ([docs/modules/capture.md](/docs/modules/capture.md)): observe with retries and paged_scan.
- Graph ([docs/modules/graph_orchestrator.md](/docs/modules/graph_orchestrator.md) + node_*.py): nodes split by file; thin facade [docs/modules/langgraph_loop.md](/docs/modules/langgraph_loop.md) builds/executes.
- State/helpers ([docs/modules/graph_state.md](/docs/modules/graph_state.md)): GraphState TypedDict, hashes, classifiers (goal/page/task), scoring, records, terminal mapping.
- Planner ([docs/modules/planner.md](/docs/modules/planner.md) + node_planner): LLM with strict schema and rich context.
- Execute ([docs/modules/execute.md](/docs/modules/execute.md) + node_execute): action execution with fallbacks, tab/context event handling.
- Observe ([docs/modules/observe.md](/docs/modules/observe.md) + node_observe): Set-of-Mark JS, overlay, goal-aware retries for sparse listings.
- Safety/confirm ([docs/modules/security.md](/docs/modules/security.md) + node_safety/confirm): risk analysis + confirmations.
- Progress (node_progress): progress scoring, auto done/ask_user, no-progress counters.
- UX ([docs/modules/ux_narration.md](/docs/modules/ux_narration.md), [docs/modules/ui_shell.md](/docs/modules/ui_shell.md)): UX messages; optional interactive shell.

Flows
-----
- LangGraph: observe → (loop_mitigation if loop_trigger) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END; error_retry after planner/execute errors/timeouts/disallowed.
- Terminals normalized by termination_normalizer to terminal_reason/type.
- Initial state sets goal_kind/stage, counters, tabs/tab_events, intent/ux/context_events.

See also
--------
- [docs/modules/langgraph_loop.md](/docs/modules/langgraph_loop.md) for node wiring and flow edges.
- [docs/modules/termination_normalizer.md](/docs/modules/termination_normalizer.md) for terminal mapping.

State Tracing/Artifacts
-----------------------
- data/state: planner/execute JSON, labels session/step; observe mapping/screenshot paths.
- logs/trace.jsonl: node records/summary.
- logs/agent.log: text events.
- UX messages and intent_history kept in GraphState (for reports; not used in logic).
