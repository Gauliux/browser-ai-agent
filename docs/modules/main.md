Module: src/main.py
===================

Responsibility
--------------
- CLI entrypoint: parse flags/env overrides, load Settings, start BrowserRuntime, select LangGraph or legacy loop, optional UI shell.
- Manages goals queue and clean-between-goals option; keeps browser open when no key/goal.

Key Behavior
------------
- apply_cli_overrides mutates Settings/env (execute, timeouts, limits, overlay, paged_scan, auto_done, viewport sync, conservative_observe, reobserve/attempt limits, scroll_step).
- Chooses use_langgraph from flag or USE_LANGGRAPH env; legacy loop used only as fallback.
- For each goal: optionally clean logs/state/screenshots; build LangGraph runner (TextLogger/TraceLogger if available) and invoke; print stop_reason/url.
- UI shell: builds runner (prefers LangGraph), passes to ui_shell.run_ui_shell with optional step limit copy of settings.

Interactions/Deps
-----------------
- Settings.load (config/config), BrowserRuntime (infra/runtime), Planner (core/planner), AgentLoop/AgentState (legacy), langgraph_loop.build_graph, TextLogger/TraceLogger (infra/tracing), ui_shell.run_ui_shell.

CLI Flags
---------
- Supports all configuration overrides; see docs/configuration.md for list.
