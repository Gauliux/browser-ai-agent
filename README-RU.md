Браузерный AI агент
===================
Headful Playwright + OpenAI (function-calling) агент, оркестрируемый LangGraph. Использует DOM Set-of-Mark для наблюдения, планирует по строгой схеме tool call, исполняется с простыми фолбэками и пишет артефакты (JSON, скриншоты, трейс).

Демо
----
<img src="demo.gif" alt="UwU gif demo OwO">

Стек
----
- Python 3.10+ (async)
- Playwright Chromium (headful, persistent profile)
- OpenAI SDK (function-calling)
- LangGraph (оркестрация графа)
- jsonschema, python-dotenv

Дорожная карта документации
---------------------------
- Быстрый старт: [docs/setup.md](/docs/setup.md) (установка/запуск) → [docs/configuration.md](/docs/configuration.md) (env/CLI справочник).
- Обзор системы: [docs/architecture.md](/docs/architecture.md) (компоненты/потоки) и [docs/structure.md](/docs/structure.md) (структура репо).
- Поведение: [docs/agent_logic.md](/docs/agent_logic.md) (FSM, цикл), [docs/browser_integration.md](/docs/browser_integration.md) (Playwright + Set-of-Mark), [docs/llm_handoff.md](/docs/llm_handoff.md) (контракт планера), [docs/logging_artifacts.md](/docs/logging_artifacts.md) (артефакты).
- Внутренности модулей: `docs/modules/` — начните с [langgraph_loop.md](/docs/modules/langgraph_loop.md) (сборка графа), далее [observe.md](/docs/modules/observe.md), [planner.md](/docs/modules/planner.md), [execute.md](/docs/modules/execute.md), [loop.md](/docs/modules/loop.md) (legacy), [runtime.md](/docs/modules/runtime.md), [security.md](/docs/modules/security.md), [capture.md](/docs/modules/capture.md), [graph_state.md](/docs/modules/graph_state.md), [graph_orchestrator.md](/docs/modules/graph_orchestrator.md), [ui_shell.md](/docs/modules/ui_shell.md), [ux_narration.md](/docs/modules/ux_narration.md), [termination_normalizer.md](/docs/modules/termination_normalizer.md), [state.md](/docs/modules/state.md) (legacy buffer).
- Ограничения и планы: [docs/limitations_todo.md](/docs/limitations_todo.md) (что не покрыто) и [docs/rationale.md](/docs/rationale.md) (компромиссы).
- Концепция Plan B (RFC): [docs/plan_b.md](/docs/plan_b.md) про StrategyProfile (декларативно, без DOM-логики).

Как работает сейчас
-------------------
- По умолчанию: LangGraph всегда включён; legacy включается только если граф не инициализировался. Исполнение включено; `--plan-only` его отключает.
- FSM/терминалы: стадии orient → context → locate → verify → done; терминалы фиксированы (goal_satisfied, goal_failed, loop_stuck, budget_exhausted).
- Вкладки/типы страниц: нет авто-переключения вкладок (только action switch_tab); тип страницы — эвристика listing/detail; автотестов и моков нет.
- Цикл (узлы LangGraph):
  1) observe (node_observe/observe.py): снимает DOM mapping (Set-of-Mark), опц. скрин, хэши для loop/stagnation, метаданные вкладок.
  2) loop_mitigation (node_loop_mitigation): опц. «консервативное» observe, затем paged_scan с boost mapping до max_auto_scrolls.
  3) goal_check (node_goal_check): повышает стадию, ставит терминалы по целям/бюджетам/лупу, классифицирует page_type.
  4) planner (node_planner/planner.py): собирает контекст (goal/stage/page_type/tabs/candidates/errors/loop) и вызывает OpenAI tool schema.
  5) safety (node_safety/security.py): эвристика риска (ключевые слова, карты, рискованные домены/пути).
  6) confirm (node_confirm): запрашивает/авто-подтверждает при необходимости (auto_confirm обходит).
  7) execute (node_execute/execute.py): исполняет действие с фолбэками (reobserve+scroll wiggle → JS click → text-match), обрабатывает switch_tab, пишет контекстные события.
  8) progress (node_progress): считает прогресс, auto_done/ask_user по настройкам/стадии, обновляет repeat/no-progress/planner_calls/step.
  9) ask_user (node_ask_user): интерактивно только при INTERACTIVE_PROMPTS=true, иначе сразу пишет stop_reason.
  10) error_retry (node_error_retry): один повтор после ошибок/таймаутов planner/execute/disallowed.
  Поток: START → observe → (loop_mitigation?) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.

Установка
---------
1) Установить зависимости:
```
pip install playwright openai jsonschema python-dotenv
playwright install chromium
```
2) Создать `.env` в корне:
```
OPENAI_API_KEY=ваш_ключ
OPENAI_MODEL=модель
```
Остальные переменные — опционально.

Запуск
------
Базово:
`python src/main.py` или `python src/main.py --goal "Найди товар"`

Полезные флаги:
- `--hide-overlay` скрыть оверлей
- `--clean-between-goals` чистить logs/state/screenshots между целями
- `--ui-shell` интерактивная оболочка поверх графа
- `--plan-only` отключить исполнение (только план/отладка)
- `--auto-confirm` пропуск подтверждений (осторожно)

Артефакты и логи
----------------
- data/state: observation-*.json, planner-*.json (raw при ENABLE_RAW_LOGS), execute-*.json
- data/screenshots: observe-*.png, exec-*.png, exec-js-click/text-click
- data/user_data: persistent профиль браузера
- logs/agent.log, logs/trace.jsonl (если доступны)

Конфигурация (Env / .env / CLI)
--------------------------------
Приоритет: CLI > .env > env. Полный список: [docs/configuration.md](/docs/configuration.md).

Env / .env (ключевые):
- `OPENAI_API_KEY` (обязательно), `OPENAI_MODEL`, `OPENAI_BASE_URL`
- `START_URL` (about:blank), `HEADLESS` (`true`|`false`)
- `MAPPING_LIMIT` (int)
- `PLANNER_SCREENSHOT_MODE` (`auto`|`always`|`never`; по умолчанию auto)
- `OBSERVE_SCREENSHOT_MODE` (`on_demand`|`always`; по умолчанию on_demand)
- Бюджеты/таймауты: `MAX_STEPS`, `PLANNER_TIMEOUT_SEC`, `EXECUTE_TIMEOUT_SEC`, `MAX_PLANNER_CALLS`, `MAX_NO_PROGRESS_STEPS`
- Loop: `LOOP_REPEAT_THRESHOLD`, `STAGNATION_THRESHOLD`, `MAX_AUTO_SCROLLS`, `LOOP_RETRY_MAPPING_BOOST`, `PAGED_SCAN_STEPS`, `PAGED_SCAN_VIEWPORTS`, `CONSERVATIVE_OBSERVE`
- Safety/UX: `AUTO_CONFIRM`, `INTERACTIVE_PROMPTS`, `PROGRESS_KEYWORDS`, `AUTO_DONE_MODE`, `AUTO_DONE_THRESHOLD`, `AUTO_DONE_REQUIRE_URL_CHANGE`
- Устойчивость исполнения: `MAX_REOBSERVE_ATTEMPTS`, `MAX_ATTEMPTS_PER_ELEMENT`, `SCROLL_STEP`, `TYPE_SUBMIT_FALLBACK`
- Overlay/view: `HIDE_OVERLAY`, `VIEWPORT_WIDTH/HEIGHT`, `SYNC_VIEWPORT_WITH_WINDOW`
- Пути: `USER_DATA_DIR`, `SCREENSHOTS_DIR`, `STATE_DIR`, `LOGS_DIR`
- Security: `SENSITIVE_PATHS`, `RISKY_DOMAINS`

CLI-флаги (override env):
- `--goal` / `--goals`
- `--plan-only` отключает исполнение
- `--auto-confirm`
- Время/бюджеты: `--max-steps`, `--planner-timeout`, `--execute-timeout`, `--max-planner-calls`, `--max-no-progress-steps`
- Mapping/loop: `--mapping-limit`, `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`, `--paged-scan-steps`, `--paged-scan-viewports`, `--conservative-observe`
- Скриншоты/overlay: `--screenshot-mode` (planner: `auto`|`always`|`never`), `--observe-screenshot-mode` (observe: `on_demand`|`always`), `--hide-overlay`
- Auto-done: `--auto-done-mode`, `--auto-done-threshold`, `--auto-done-require-url-change`
- Viewport/scroll: `--sync-viewport` / `--no-sync-viewport`, `--scroll-step`, `--max-reobserve-attempts`, `--max-attempts-per-element`
- Workflow: `--clean-between-goals`, `--ui-shell`, `--ui-step-limit`
