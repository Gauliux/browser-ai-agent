Module: src/agent/paths.py
==========================

Responsibility
--------------
- Resolve filesystem paths for data/logs based on project root and env overrides.
- Ensure directories exist.

Key Structures
--------------
- Paths dataclass: root, user_data_dir, screenshots_dir, state_dir, logs_dir.

Behavior
--------
- from_env(root): builds paths; supports USER_DATA_DIR, SCREENSHOTS_DIR, STATE_DIR, LOGS_DIR overrides; defaults under <root>/data and <root>/logs.
- ensure(): creates all directories.
