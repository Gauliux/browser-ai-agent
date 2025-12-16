Repository Structure
====================

Top-level
---------
- src/main.py — CLI entrypoint, runs LangGraph loop or legacy loop (legacy frozen).
- src/agent/* — core agent modules (runtime, observe, planner, execute, security, LangGraph loop, tracing, UI shell, config, paths, state).
- data/… — user_data (browser profile), screenshots, state artifacts (created at runtime).
- logs/… — agent.log, trace.jsonl (created at runtime).
- docs/… — project documentation (this set).
- Legacy/test: src/agent/loop.py (legacy loop, not developed), src/agent/ui_tkinter.py (test UI).

Key Module Responsibilities
---------------------------
- config.py — load env/CLI settings, clamp values, paths setup.
- paths.py — resolve data/log folders (env overrides), ensure dirs.
- runtime.py — Playwright headful persistent browser, active page tracking, TargetClosed resilience, tab hint selection.
- observe.py — DOM annotation (Set-of-Mark), overlay, zone balancing, optional screenshot, paged_scan helper.
- planner.py — OpenAI function-calling planner with strict schema and rich context; loads recent observations.
- execute.py — Execute planner actions with fallbacks, per-element limits, screenshots, unified labels.
- security.py — Heuristics for destructive actions, confirmation prompt/auto-confirm.
- langgraph_loop.py — Full LangGraph state graph, FSM/stages/terminals, loop mitigation, progress, retries.
- tracing.py — Text/JSONL logging helpers, step id.
- ui_shell.py — Optional interactive supervisor loop.
- state.py — Sliding window for legacy loop (kept for completeness).
- main.py — CLI/flags/env overrides, runtime startup, goal queue, selects LangGraph or legacy, optional UI shell.

Artifacts/Logs
--------------
- data/state — observation/planner/execute JSONs (labeled with session/step), per run.
- data/screenshots — observe/exec screenshots (session/step in name).
- logs/agent.log — text log.
- logs/trace.jsonl — structured trace lines (if enabled).
- data/user_data — persistent browser profile.
