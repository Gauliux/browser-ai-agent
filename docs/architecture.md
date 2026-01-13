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
- Runtime (infra/runtime.py): browser lifecycle, active tab tracking, TargetClosed resilience, tab metadata.
- Capture (infra/capture.py): observe with retries and paged_scan.
- Graph (core/graph_orchestrator.py + node_*.py): nodes split by file; thin facade langgraph_loop.py builds/executes.
- State/helpers (core/graph_state.py): GraphState TypedDict, hashes, classifiers (goal/page/task), scoring, records, terminal mapping.
- Planner (core/planner.py + node_planner): LLM with strict schema and rich context.
- Execute (core/execute.py + node_execute): action execution with fallbacks, tab/context event handling.
- Observe (core/observe.py + node_observe): Set-of-Mark JS, overlay, goal-aware retries for sparse listings.
- Safety/confirm (core/security.py + node_safety/confirm): risk analysis + confirmations.
- Progress (node_progress): progress scoring, auto done/ask_user, no-progress counters.
- UX (io/ux_narration.py, io/ui_shell.py): UX messages; optional interactive shell.

Flows
-----
- LangGraph: observe → (loop_mitigation if loop_trigger) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END; error_retry after planner/execute errors/timeouts/disallowed.
- Terminals normalized by termination_normalizer to terminal_reason/type.
- Initial state sets goal_kind/stage, counters, tabs/tab_events, intent/ux/context_events.

State Tracing/Artifacts
-----------------------
- data/state: planner/execute JSON, labels session/step; observe mapping/screenshot paths.
- logs/trace.jsonl: node records/summary.
- logs/agent.log: text events.
- UX messages and intent_history kept in GraphState (for reports; not used in logic).
