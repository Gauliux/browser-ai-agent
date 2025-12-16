Module: src/agent/runtime.py
============================

Responsibility
--------------
- Manage Playwright browser lifecycle (headful persistent Chromium).
- Track and switch the active page; handle TargetClosed/closed tabs.
- Provide helpers to select pages by hint (URL/title/index).

Key Behavior
------------
- launch(): start Playwright, launch_persistent_context with user_data_dir, headless flag, optional viewport (from settings), args --start-maximized; attach page close/new listeners; open start_url.
- ensure_page(): return active alive page, otherwise pick last alive tab, otherwise create a new tab; relaunch if context missing.
- set_active_page(): set current page and store guid (best effort).
- set_active_page_by_hint(url_substr/title_substr/index): find matching alive page and make it active.
- TargetClosed detection: is_target_closed_error checks exception messages; used by callers to retry observe/execute after tab closure.
- get_pages_meta(): debug helper to list pages (index/url/title/closed/active).
- close(): graceful shutdown (ignore errors if already closed); idle(): block until cancelled.

Settings Used
-------------
- headless, viewport_width/viewport_height (optional), start_url.
- paths.user_data_dir (persistent profile).

Integration Points
------------------
- Called from main.py to start runtime.
- Used by langgraph_loop observe/execute nodes to recover from closed tabs and to honor switch_tab hints.
