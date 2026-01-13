Module: src/main.py
===================

Responsibility
--------------
- CLI entrypoint: parse flags/env overrides, load Settings, start BrowserRuntime, prefer LangGraph (legacy only as fallback), optional UI shell.
- Manages goals queue and clean-between-goals option; keeps browser open when no key/goal.

Key Behavior
------------
- apply_cli_overrides mutates Settings/env (timeouts, limits, overlay, paged_scan, auto_done, viewport sync, conservative_observe, reobserve/attempt limits, scroll_step); execution is enabled by default, `--plan-only` disables it.
- LangGraph is the default; legacy loop used only as fallback.
- For each goal: optionally clean logs/state/screenshots; build LangGraph runner (TextLogger/TraceLogger if available) and invoke; print stop_reason/url.
- UI shell: builds runner (prefers LangGraph), passes to ui_shell.run_ui_shell with optional step limit copy of settings.

Interactions/Deps
-----------------
- Settings.load (config/config), BrowserRuntime (infra/runtime), Planner (core/planner), AgentLoop/AgentState (legacy), langgraph_loop.build_graph, TextLogger/TraceLogger (infra/tracing), ui_shell.run_ui_shell.

CLI Flags
---------
- Supports all configuration overrides; see docs/configuration.md for list.
