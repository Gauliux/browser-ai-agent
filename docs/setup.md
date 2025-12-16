Setup and Running
=================

Prerequisites
-------------
- Python 3.10+ (recommended 3.11+).
- Playwright browser binaries installed.
- OpenAI API key.

Installation
------------
1) Install dependencies (example):
   ```bash
   pip install -r requirements.txt  # if present
   # or manually
   pip install playwright openai jsonschema python-dotenv
   playwright install chromium
   ```
2) Create `.env` with `OPENAI_API_KEY=...` and optional overrides (see configuration.md).

First Run (LangGraph)
---------------------
```bash
python src/main.py --goal "My goal" --langgraph --execute
```
- Add `--clean-between-goals` to wipe logs/state/screenshots between goals.
- Add `--hide-overlay` if overlays bother you.

UI Shell (optional)
-------------------
```bash
python src/main.py --ui-shell --langgraph --execute
```
- Use `--ui-step-limit` to cap steps in UI shell mode only.

Environment Tips
----------------
- Set `INTERACTIVE_PROMPTS=true` for interactive ask_user/progress prompts.
- Set `AUTO_CONFIRM=true` to skip safety confirmations (use with care).
- Override data/logs paths if needed: USER_DATA_DIR, STATE_DIR, SCREENSHOTS_DIR, LOGS_DIR.

Troubleshooting
---------------
- If browser fails to open: ensure Playwright installed (`playwright install chromium`).
- If OpenAI errors: verify OPENAI_API_KEY and network access; planner_timeout/execute_timeout adjustable.
- If artifacts clutter: use `--clean-between-goals` or delete data/screenshots/state/logs.
