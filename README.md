Browser LangGraph Agent
=======================

Demo
----

<img src="demo.gif" alt="UwU gif demo OwO">

Overview
--------
A headful, persistent Playwright + OpenAI (function-calling) agent orchestrated by LangGraph. It observes pages via a DOM Set-of-Mark overlay, plans with a strict tool schema, executes actions with resilient fallbacks, and logs artifacts (JSON + screenshots + traces). Focus is on a universal strategy-driven agent (Plan B), not site-specific logic.

Tech Stack
----------
- Python 3.10+ (async)
- Playwright Chromium (headful, persistent profile)
- OpenAI SDK (function-calling)
- LangGraph (graph orchestration)
- jsonschema, python-dotenv

Current State / Characteristics
-------------------------------
- Primary loop: LangGraph; legacy custom loop remains only as a fallback.
- Fixed FSM stages: orient → context → locate → verify → done.
- Fixed terminals: goal_satisfied, goal_failed, loop_stuck, budget_exhausted.
- No automated tab selection (switch_tab is explicit). Page type heuristic is listing/detail only. No automated tests/mock pages yet.

Execution Cycle (LangGraph)
---------------------------
1) observe: capture DOM mapping (Set-of-Mark), optional screenshot, loop/stagnation detection, tab metadata.  
2) loop_mitigation: conservative observe (optional) and paged_scan with mapping boost.  
3) goal_check: stage promotion, artifact hints, terminal checks (budget/loop/goal).  
4) planner: build rich context (goal/stage/page_type/tabs/candidates/errors/loop), call OpenAI tool schema.  
5) safety: heuristic risk check (keywords, cards, risky domains/paths).  
6) confirm: user/auto confirm if required.  
7) execute: perform action with fallbacks (reobserve+scroll wiggle → JS click → text-match), handle switch_tab, record context events.  
8) progress: score evidence, auto_done/ask_user per settings/stage, update counters.  
9) ask_user: interactive only if INTERACTIVE_PROMPTS=true; otherwise auto-stop reason.  
10) error_retry: one retry after planner/execute errors/timeouts/disallowed.  
Flow: START → observe → (loop_mitigation?) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.

Artifacts & Logs
----------------
- data/state: observation-*.json, planner-*.json (raw if enabled), execute-*.json
- data/screenshots: observe-*.png, exec-*.png, exec-js-click/text-click
- data/user_data: persistent browser profile
- logs/agent.log, logs/trace.jsonl (if available)

Setup
-----
1) Install deps:
```
pip install -r requirements.txt  # if present
# or minimal set
pip install playwright openai jsonschema python-dotenv
playwright install chromium
```
2) Create `.env` in repo root with at least:
```
OPENAI_API_KEY=your_key_here
```
Optional overrides below.

Running
-------
Basic (LangGraph is default, execution on):
```
python src/main.py --goal "Find the product"
```
(`--langgraph` is no longer needed; LangGraph is always used and legacy runs only as a fallback on failures.)
Useful flags:
- `--hide-overlay` to hide DOM badges
- `--clean-between-goals` to wipe logs/state/screenshots per goal
- `--ui-shell` to run the interactive shell wrapper (uses same graph)
- `--plan-only` to disable execution (plan/debug only)
- `--auto-confirm` to skip safety confirmation (use with care)

Using UI Shell
--------------
```
python src/main.py --ui-shell
```
- Honors `INTERACTIVE_PROMPTS` for ask_user/confirm flow.
- `--ui-step-limit` can cap steps for UI shell runs only.

Configuration (Env / .env / CLI overrides)
------------------------------------------
Priority: CLI > .env > process env. Key options:
- OPENAI_API_KEY, OPENAI_MODEL (default gpt-4o-mini), OPENAI_BASE_URL
- START_URL (default about:blank), HEADLESS (default false)
- MAPPING_LIMIT (default 30)
- PLANNER_SCREENSHOT_MODE (auto|always|never; default auto)
- MAX_STEPS (default 6), PLANNER_TIMEOUT_SEC (25), EXECUTE_TIMEOUT_SEC (20)
- AUTO_CONFIRM (false), ENABLE_RAW_LOGS (true)
- LOOP_REPEAT_THRESHOLD (2), STAGNATION_THRESHOLD (2), MAX_AUTO_SCROLLS (3), LOOP_RETRY_MAPPING_BOOST (20)
- PROGRESS_KEYWORDS (comma-separated)
- AUTO_DONE_MODE (ask|auto), AUTO_DONE_THRESHOLD (2), AUTO_DONE_REQUIRE_URL_CHANGE (true)
- PAGED_SCAN_STEPS (2), PAGED_SCAN_VIEWPORTS (2)
- OBSERVE_SCREENSHOT_MODE (on_demand|always; default on_demand)
- HIDE_OVERLAY (false)
- VIEWPORT_WIDTH/HEIGHT, SYNC_VIEWPORT_WITH_WINDOW (false)
- TYPE_SUBMIT_FALLBACK (true)
- CONSERVATIVE_OBSERVE (false)
- MAX_REOBSERVE_ATTEMPTS (1), MAX_ATTEMPTS_PER_ELEMENT (3), SCROLL_STEP (600)
- MAX_PLANNER_CALLS (20), MAX_NO_PROGRESS_STEPS (20)
- INTERACTIVE_PROMPTS (false)
- Path overrides: USER_DATA_DIR, SCREENSHOTS_DIR, STATE_DIR, LOGS_DIR
- Security lists: SENSITIVE_PATHS, RISKY_DOMAINS
- USE_LANGGRAPH (enable graph; default is on)

Parameter reference (quick)
---------------------------
Env / .env (key ones, with values):
- `OPENAI_API_KEY` (required), `OPENAI_MODEL` (default gpt-4o-mini), `OPENAI_BASE_URL`
- `START_URL` (default about:blank), `HEADLESS` (true|false)
- `MAPPING_LIMIT` (int)
- `PLANNER_SCREENSHOT_MODE` (auto|always|never; default auto)
- `OBSERVE_SCREENSHOT_MODE` (on_demand|always; default on_demand)
- Budgets/timeouts: `MAX_STEPS`, `PLANNER_TIMEOUT_SEC`, `EXECUTE_TIMEOUT_SEC`, `MAX_PLANNER_CALLS`, `MAX_NO_PROGRESS_STEPS`
- Loop: `LOOP_REPEAT_THRESHOLD`, `STAGNATION_THRESHOLD`, `MAX_AUTO_SCROLLS`, `LOOP_RETRY_MAPPING_BOOST`, `PAGED_SCAN_STEPS`, `PAGED_SCAN_VIEWPORTS`, `CONSERVATIVE_OBSERVE` (true|false)
- Safety/UX: `AUTO_CONFIRM` (true|false), `INTERACTIVE_PROMPTS` (true|false), `PROGRESS_KEYWORDS`, `AUTO_DONE_MODE` (ask|auto), `AUTO_DONE_THRESHOLD` (int), `AUTO_DONE_REQUIRE_URL_CHANGE` (true|false)
- Execution resilience: `MAX_REOBSERVE_ATTEMPTS`, `MAX_ATTEMPTS_PER_ELEMENT`, `SCROLL_STEP`, `TYPE_SUBMIT_FALLBACK` (true|false)
- Overlay/view: `HIDE_OVERLAY` (true|false), `VIEWPORT_WIDTH/HEIGHT` (ints), `SYNC_VIEWPORT_WITH_WINDOW` (true|false)
- Paths: `USER_DATA_DIR`, `SCREENSHOTS_DIR`, `STATE_DIR`, `LOGS_DIR`
- Security: `SENSITIVE_PATHS`, `RISKY_DOMAINS`

CLI Flags (override env)
------------------------
- `--goal` / `--goals` (queue)
- `--plan-only` (disable execution; default is execute enabled)
- `--auto-confirm`
- `--max-steps`, `--planner-timeout`, `--execute-timeout`
- `--screenshot-mode` (planner: auto|always|never), `--observe-screenshot-mode` (observe: on_demand|always)
- `--mapping-limit`
- `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`
- `--hide-overlay`
- `--paged-scan-steps`, `--paged-scan-viewports`
- `--auto-done-mode`, `--auto-done-threshold`, `--auto-done-require-url-change`
- `--sync-viewport` / `--no-sync-viewport`
- `--clean-between-goals`
- `--ui-shell`, `--ui-step-limit`
- `--conservative-observe`
- `--max-reobserve-attempts`, `--max-attempts-per-element`, `--scroll-step`

CLI reference (summary):
- `--goal`/`--goals` set target(s)
- `--plan-only` disables execution (plan/debug)
- `--auto-confirm` bypasses safety confirmation
- Time/budgets: `--max-steps`, `--planner-timeout`, `--execute-timeout`, `--max-planner-calls`, `--max-no-progress-steps`
- Mapping/loop: `--mapping-limit`, `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`, `--paged-scan-steps`, `--paged-scan-viewports`, `--conservative-observe`
- Screenshots/overlay: `--screenshot-mode` (planner: auto|always|never), `--observe-screenshot-mode` (observe: on_demand|always), `--hide-overlay`
- Auto-done: `--auto-done-mode`, `--auto-done-threshold`, `--auto-done-require-url-change`
- Viewport/scroll: `--sync-viewport`/`--no-sync-viewport`, `--scroll-step`, `--max-reobserve-attempts`, `--max-attempts-per-element`
- Workflow: `--clean-between-goals`, `--ui-shell`, `--ui-step-limit`
