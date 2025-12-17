Module: src/agent/infra/runtime.py
==================================

Responsibility
--------------
- Manage Playwright browser lifecycle (headful persistent Chromium).
- Track/switch active page; handle TargetClosed/closed tabs; surface tab metadata.
- Provide helpers to select pages by hint (URL/title/index) and report context events.

Key Behavior
------------
- launch(): start Playwright, launch_persistent_context with user_data_dir, headless flag, optional viewport (settings), args --start-maximized; attach page close/new listeners; open start_url.
- ensure_page(): return active alive page, otherwise pick last alive tab, otherwise create new; relaunch if context missing.
- set_active_page(): set current page and store guid (best effort).
- _handle_new_page/_handle_page_close: keep active page consistent, log page switches.
- get_pages_meta(): list pages (index/id/url/title/closed/active) for state recording.
- is_target_closed_error(): heuristic to detect closed targets for retries.
- idle()/close(): graceful shutdown.

Settings Used
-------------
- headless, viewport_width/height, start_url, sync_viewport_with_window, paths.user_data_dir.

Integration Points
------------------
- langgraph observe/execute nodes call ensure_page, get_pages_meta.
- Switch-tab actions rely on set_active_page and tabs metadata to avoid treating tab switches как ошибки.
