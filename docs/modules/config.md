Module: src/agent/config/config.py
==================================

Responsibility
--------------
- Load environment variables (.env if available), clamp numeric values, set defaults, build Settings dataclass.
- Resolve paths via Paths.from_env and ensure directories exist.

Key Settings (see configuration.md for full list)
-------------------------------------------------
- API/model/base_url; start_url; headless; mapping_limit; screenshot modes; timeouts; auto_confirm; raw logs flag.
- Loop thresholds, paged_scan settings, auto_done settings.
- Overlay/viewport/sync flags; type_submit_fallback; conservative_observe.
- Fallback budgets: max_reobserve_attempts, max_attempts_per_element, scroll_step.
- Budgets: max_planner_calls, max_no_progress_steps, max_steps.
- Paths: user_data_dir, screenshots_dir, state_dir, logs_dir.

Notable Behavior
----------------
- .env берётся из корня репозитория и загружается с override=True (приоритет: CLI → .env → env).
- clamp_int гарантирует минимумы; enum поля нормализуются.
- sync_viewport_with_window default false; hide_overlay default false.

Outputs
-------
- Settings dataclass с Paths; директории ensure().
