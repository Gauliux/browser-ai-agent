Repository Structure
====================

Top-level
---------
- src/main.py - CLI entrypoint; starts LangGraph (legacy loop kept only as fallback).
- src/agent/core - graph nodes, graph_state/orchestrator, core observe/planner/execute/security.
- src/agent/infra - runtime, capture, tracing, paths, termination_normalizer.
- src/agent/io - ui_shell and UX narration.
- src/agent/config - Settings (.env/env/CLI) and Paths loader.
- src/agent/legacy - old loop/state (kept for compatibility).
- docs/ - documentation.
- data/ - user_data (browser profile), screenshots, state artifacts (created at runtime).
- logs/ - agent.log, trace.jsonl (created at runtime).

Key Module Responsibilities
---------------------------
- config/config.py - load settings (priority CLI -> .env -> env), clamp values, init Paths.
- infra/paths.py - resolve directories (env overrides), ensure dirs exist.
- infra/runtime.py - Playwright headful persistent browser, active tab tracking, TargetClosed resilience.
- infra/capture.py - observe pass with retries, paged_scan.
- infra/tracing.py - Text/JSONL loggers, step id helper.
- infra/termination_normalizer.py - normalize LangGraph terminals.
- core/graph_state.py - GraphState TypedDict + helpers (hashes, scoring, classifiers, records).
- core/graph_orchestrator.py - compile node graph.
- core/node_*.py - observe/loop_mitigation/goal_check/planner/safety/confirm/execute/progress/ask_user/error_retry.
- core/observe.py / planner.py / execute.py / security.py - functional blocks used by nodes.
- io/ui_shell.py - optional interactive supervisor; io/ux_narration.py - UX log helper.
- langgraph_loop.py - thin facade: builds nodes/graph, runs with recursion_limit, normalizes terminal.
- legacy/loop.py, legacy/state.py - frozen legacy loop/state.
- main.py - CLI/flags/env overrides, runtime startup, goal queue, LangGraph/legacy/UI shell selection.

Artifacts/Logs
--------------
- data/state - observation/planner/execute JSONs (per session/step).
- data/screenshots - observe/exec screenshots (session/step in name).
- logs/agent.log - text log.
- logs/trace.jsonl - structured trace (if enabled).
- data/user_data - persistent browser profile.
