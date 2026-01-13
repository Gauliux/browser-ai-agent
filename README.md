Browser AI Agent
=======================
A headful Playwright + OpenAI (function-calling) browser agent orchestrated by LangGraph. It uses a DOM Set-of-Mark overlay for observation, plans via a strict tool schema, and executes with simple fallbacks while logging JSON artifacts and screenshots.

Demo
----
<img src="demo.gif" alt="UwU gif demo OwO">

Tech Stack
----------
- Python 3.10+ (async)
- Playwright Chromium (headful, persistent profile)
- OpenAI SDK (function-calling)
- LangGraph (graph orchestration)
- jsonschema, python-dotenv

Documentation Roadmap
---------------------
- Quick start: [docs/setup.md](/docs/setup.md) (install/run) → [docs/configuration.md](/docs/configuration.md) (env/CLI reference).
- System overview: [docs/architecture.md](/docs/architecture.md) (components/flows) and [docs/structure.md](/docs/structure.md) (repo layout).
- Behavior specifics: [docs/agent_logic.md](/docs/agent_logic.md) (FSM, flow), [docs/browser_integration.md](/docs/browser_integration.md) (Playwright + Set-of-Mark), [docs/llm_handoff.md](/docs/llm_handoff.md) (planner contract), [docs/logging_artifacts.md](/docs/logging_artifacts.md) (what gets stored).
- Module internals: see `docs/modules/`—start with [langgraph_loop.md](/docs/modules/langgraph_loop.md) (graph wiring), then [observe.md](/docs/modules/observe.md), [planner.md](/docs/modules/planner.md), [execute.md](/docs/modules/execute.md), [loop.md](/docs/modules/loop.md) (legacy context), [runtime.md](/docs/modules/runtime.md) (browser lifecycle), [security.md](/docs/modules/security.md), [capture.md](/docs/modules/capture.md), [graph_state.md](/docs/modules/graph_state.md), [graph_orchestrator.md](/docs/modules/graph_orchestrator.md), [ui_shell.md](/docs/modules/ui_shell.md), [ux_narration.md](/docs/modules/ux_narration.md), [termination_normalizer.md](/docs/modules/termination_normalizer.md), [state.md](/docs/modules/state.md) (legacy state buffer).
- Limits and future work: [docs/limitations_todo.md](/docs/limitations_todo.md) (current gaps) and [docs/rationale.md](/docs/rationale.md) (design trade-offs).
- Plan B concept (architecture RFC): [docs/plan_b.md](/docs/plan_b.md) for the StrategyProfile idea (declarative, no DOM logic).

How it works now
----------------
- Defaults: LangGraph loop is always used; legacy loop is a fallback only if LangGraph fails to initialize. Execution is enabled by default; `--plan-only` turns actions off.
- FSM/terminals: stages orient → context → locate → verify → done; terminals are fixed (goal_satisfied, goal_failed, loop_stuck, budget_exhausted).
- Tabs/page types: no auto tab switching (only switch_tab action); page type heuristic is listing/detail; no automated tests/mock pages yet.
- Cycle (LangGraph nodes):
  1) observe (node_observe/observe.py): capture DOM mapping (Set-of-Mark), optional screenshot, hashes for loop/stagnation, tab metadata.
  2) loop_mitigation (node_loop_mitigation): optional conservative observe, then paged_scan with mapping boost up to max_auto_scrolls.
  3) goal_check (node_goal_check): stage promotion, artifact hints, terminal checks (budget/loop/goal), page_type heuristic.
  4) planner (node_planner/planner.py): build rich context (goal/stage/page_type/tabs/candidates/errors/loop) and call OpenAI tool schema.
  5) safety (node_safety/security.py): heuristic risk check (keywords, cards, risky domains/paths).
  6) confirm (node_confirm): user/auto confirm if required (auto_confirm bypass).
  7) execute (node_execute/execute.py): perform action with fallbacks (reobserve+scroll wiggle → JS click → text-match), handle switch_tab, record context events.
  8) progress (node_progress): score evidence, auto_done/ask_user per settings/stage, update repeat/no-progress/planner_calls/step counters.
  9) ask_user (node_ask_user): interactive only if INTERACTIVE_PROMPTS=true; otherwise records stop_reason immediately.
  10) error_retry (node_error_retry): one retry after planner/execute errors/timeouts/disallowed.
  Flow: START → observe → (loop_mitigation?) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.

Setup
-----
1) Install deps:
```
pip install -r requirements.txt
# or minimal set
pip install playwright openai jsonschema python-dotenv
playwright install chromium
```
2) Create `.env` in repo root with at least:
```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=chosen_model
```
Optional overrides below.

Running
-------
Basic:
`python src/main.py` or `python src/main.py --goal "Find the product"`

Useful flags:
- `--hide-overlay` to hide DOM badges
- `--clean-between-goals` to wipe logs/state/screenshots per goal
- `--ui-shell` to run the interactive shell wrapper (uses same graph)
- `--plan-only` to disable execution (plan/debug only)
- `--auto-confirm` to skip safety confirmation (use with care)

Artifacts & Logs
----------------
- data/state: observation-*.json, planner-*.json (raw if enabled), execute-*.json
- data/screenshots: observe-*.png, exec-*.png, exec-js-click/text-click
- data/user_data: persistent browser profile
- logs/agent.log, logs/trace.jsonl (if available)

Configuration (Env / .env / CLI flags)
------------------------------------------
Priority: CLI > .env > process env.
Full lists at [docs/configuration.md](/docs/configuration.md).

Env / .env (key ones, with values):
- `OPENAI_API_KEY` (required), `OPENAI_MODEL`, `OPENAI_BASE_URL`
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

CLI flags (override env):
- `--goal`/`--goals` (queue)
- `--plan-only` disable execution
- `--auto-confirm` bypasses safety confirmation
- Time/budgets: `--max-steps`, `--planner-timeout`, `--execute-timeout`, `--max-planner-calls`, `--max-no-progress-steps`
- Mapping/loop: `--mapping-limit`, `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`, `--paged-scan-steps`, `--paged-scan-viewports`, `--conservative-observe`
- Screenshots/overlay: `--screenshot-mode` (planner: auto|always|never), `--observe-screenshot-mode` (observe: on_demand|always), `--hide-overlay`
- Auto-done: `--auto-done-mode`, `--auto-done-threshold`, `--auto-done-require-url-change`
- Viewport/scroll: `--sync-viewport`/`--no-sync-viewport`, `--scroll-step`, `--max-reobserve-attempts`, `--max-attempts-per-element`
- Workflow: `--clean-between-goals`, `--ui-shell`, `--ui-step-limit`