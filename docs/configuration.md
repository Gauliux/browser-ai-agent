Configuration and Parameters
============================

Environment Variables (defaults)
--------------------------------
- `OPENAI_API_KEY` – required for planning; without it the agent only opens the browser.
- `OPENAI_MODEL`
- `OPENAI_BASE_URL` – optional custom endpoint.
- `START_URL=about:blank`
- `HEADLESS=false` – set true for headless browser.
- `MAPPING_LIMIT=30`
- `PLANNER_SCREENSHOT_MODE=auto` (`auto|always|never`)
- `MAX_STEPS=6`
- `PLANNER_TIMEOUT_SEC=25`
- `EXECUTE_TIMEOUT_SEC=20`
- `AUTO_CONFIRM=false`
- `ENABLE_RAW_LOGS=true` – save raw planner replies.
- `LOOP_REPEAT_THRESHOLD=2`
- `STAGNATION_THRESHOLD=2`
- `MAX_AUTO_SCROLLS=3`
- `LOOP_RETRY_MAPPING_BOOST=20`
- `PROGRESS_KEYWORDS="cart,корзина,basket,checkout,add to cart,добавить в корзину,товар,product"`
- `AUTO_DONE_MODE=ask` (`ask|auto`)
- `AUTO_DONE_THRESHOLD=2`
- `AUTO_DONE_REQUIRE_URL_CHANGE=true`
- `PAGED_SCAN_STEPS=2`
- `PAGED_SCAN_VIEWPORTS=2`
- `OBSERVE_SCREENSHOT_MODE=on_demand` (`on_demand|always`)
- `HIDE_OVERLAY=false`
- `VIEWPORT_WIDTH/VIEWPORT_HEIGHT` – optional fixed viewport.
- `SYNC_VIEWPORT_WITH_WINDOW=false`
- `TYPE_SUBMIT_FALLBACK=true`
- `CONSERVATIVE_OBSERVE=false`
- `MAX_REOBSERVE_ATTEMPTS=1`
- `MAX_ATTEMPTS_PER_ELEMENT=3`
- `SCROLL_STEP=600`
- `MAX_PLANNER_CALLS=20`
- `MAX_NO_PROGRESS_STEPS=20`
- Paths: `USER_DATA_DIR`, `SCREENSHOTS_DIR`, `STATE_DIR`, `LOGS_DIR`
- Security lists: `SENSITIVE_PATHS`, `RISKY_DOMAINS`
- `INTERACTIVE_PROMPTS=false` – gates ask_user/progress prompts.
- `USE_LANGGRAPH` – deprecated/ignored (LangGraph is always on by default).

CLI Flags (override env)
------------------------
- `--goal` / `--goals` – single or multiple goals.
- `--plan-only` – disable execution (execution is enabled by default).
- `--auto-confirm`
- `--max-steps`, `--planner-timeout`, `--execute-timeout`
- `--screenshot-mode {auto|always|never}` – planner screenshots
- `--mapping-limit`
- `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`
- `--langgraph` – deprecated; LangGraph is already the default (legacy used only on fallback).
- `--hide-overlay`
- `--paged-scan-steps`, `--paged-scan-viewports`
- `--auto-done-mode {auto|ask}`, `--auto-done-threshold`, `--auto-done-require-url-change`
- `--observe-screenshot-mode {on_demand|always}`
- `--sync-viewport` / `--no-sync-viewport`
- `--clean-between-goals`
- `--ui-shell`, `--ui-step-limit`
- `--conservative-observe`
- `--max-reobserve-attempts`
- `--max-attempts-per-element`
- `--scroll-step`

Priority
--------
CLI overrides → `.env` at repo root → process environment (loaded with override=True).

What Settings Affect
--------------------
- `INTERACTIVE_PROMPTS`: on → blocking ask_user/progress prompts; off → non-blocking.
- `AUTO_CONFIRM`: skip confirmations on risky actions.
- `mapping_limit` (+ loop boost): how many elements LLM sees → context size/tokens.
- `max_steps` / `max_planner_calls` / `max_no_progress_steps`: budgets → goal_failed/budget_exhausted terminals.
- Loop thresholds + paged_scan: when loop mitigation triggers and how deep it scans.
- `max_reobserve_attempts` / `max_attempts_per_element`: execute resilience and avoid-list growth.
- `scroll_step`: scroll magnitude in actions/fallbacks.
- `hide_overlay`: hide overlay badges; ids remain.
- Screenshot modes: frequency in observe/planner.
- Path overrides: where artifacts/logs/profile are written.
