Module: src/agent/infra/paths.py
=================================

Responsibility
--------------
- Resolve data/log directories from environment overrides and repo root.
- Ensure runtime folders exist.

Key Behavior
------------
- from_env(root): supports USER_DATA_DIR, SCREENSHOTS_DIR, STATE_DIR, LOGS_DIR.
- ensure(): creates all folders (parents=True, exist_ok=True).

Used By
-------
- config/config.py during Settings.load().
