Браузерный агент на LangGraph
=============================

Обзор
-----
Headful Playwright + OpenAI (function-calling) агент, оркестрируемый LangGraph. Наблюдает DOM через Set-of-Mark, планирует по строгой схеме tool call, исполняет действия с устойчивыми фолбэками, сохраняет артефакты (JSON + скриншоты + трейс). Фокус — универсальный агент (Plan B), без site-specific логики.

Технологии
----------
- Python 3.10+ (async)
- Playwright Chromium (headful, persistent profile)
- OpenAI SDK (function-calling)
- LangGraph (граф оркестрации)
- jsonschema, python-dotenv

Текущее состояние
-----------------
- Основной цикл: LangGraph; legacy loop оставлен лишь как fallback.
- Стадии FSM: orient → context → locate → verify → done.
- Терминалы: goal_satisfied, goal_failed, loop_stuck, budget_exhausted.
- Нет авто-выбора вкладки (switch_tab только явный). Классификация страниц — listing/detail. Тестов/моков нет.

Цикл исполнения (LangGraph)
---------------------------
1) observe: захват DOM mapping (Set-of-Mark), опциональный скрин, детекция loop/stagnation, метаданные вкладок.  
2) loop_mitigation: аккуратный проход (опция) и paged_scan с boost лимита.  
3) goal_check: повышение стадии, терминалы по целям/бюджетам/лупу.  
4) planner: собирает контекст (goal/stage/page_type/tabs/candidates/errors/loop), вызывает OpenAI tool schema.  
5) safety: эвристика риска (ключевые слова, карты, рискованные домены/пути).  
6) confirm: запрос/авто-подтверждение при необходимости.  
7) execute: действие с фолбэками (reobserve+scroll wiggle → JS click → text-match), обрабатывает switch_tab, пишет контекстные события.  
8) progress: скоринг, auto_done/ask_user по стадиям/настройкам, обновление счётчиков.  
9) ask_user: интерактивно только если INTERACTIVE_PROMPTS=true; иначе авто-stop_reason.  
10) error_retry: один повтор после planner/execute ошибок/таймаутов/disallowed.  
Поток: START → observe → (loop_mitigation?) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.

Артефакты и логи
----------------
- data/state: observation-*.json, planner-*.json (raw при ENABLE_RAW_LOGS), execute-*.json
- data/screenshots: observe-*.png, exec-*.png, exec-js-click/text-click
- data/user_data: persistent профиль браузера
- logs/agent.log, logs/trace.jsonl (если доступно)

Установка
---------
1) Установить зависимости:
```
pip install -r requirements.txt  # если есть
# или минимальный набор
pip install playwright openai jsonschema python-dotenv
playwright install chromium
```
2) Создать `.env` в корне:
```
OPENAI_API_KEY=ваш_ключ
```
Остальные переменные — опционально (см. ниже).

Запуск
------
Базово (LangGraph по умолчанию, с исполнением):
```
python src/main.py --goal "Найди товар"
```
(`--langgraph` больше не нужен; граф используется всегда, legacy включается только как fallback при ошибке.)
Полезные флаги:
- `--hide-overlay` скрыть оверлей
- `--clean-between-goals` чистить logs/state/screenshots между целями
- `--ui-shell` интерактивная оболочка поверх графа
- `--plan-only` отключить исполнение (только план/отладка)
- `--auto-confirm` пропуск подтверждений (осторожно)

UI Shell
--------
```
python src/main.py --ui-shell
```
- Уважает `INTERACTIVE_PROMPTS` в ask_user/confirm.
- `--ui-step-limit` — отдельный лимит шагов для UI shell.

Конфигурация (Env / .env / CLI)
-------------------------------
Приоритет: CLI > .env > env. Ключевые параметры:
- OPENAI_API_KEY, OPENAI_MODEL (по умолчанию gpt-4o-mini), OPENAI_BASE_URL
- START_URL (about:blank), HEADLESS (false)
- MAPPING_LIMIT (30)
- PLANNER_SCREENSHOT_MODE (auto|always|never; по умолчанию auto)
- MAX_STEPS (6), PLANNER_TIMEOUT_SEC (25), EXECUTE_TIMEOUT_SEC (20)
- AUTO_CONFIRM (false), ENABLE_RAW_LOGS (true)
- LOOP_REPEAT_THRESHOLD (2), STAGNATION_THRESHOLD (2), MAX_AUTO_SCROLLS (3), LOOP_RETRY_MAPPING_BOOST (20)
- PROGRESS_KEYWORDS (список через запятую)
- AUTO_DONE_MODE (ask|auto), AUTO_DONE_THRESHOLD (2), AUTO_DONE_REQUIRE_URL_CHANGE (true)
- PAGED_SCAN_STEPS (2), PAGED_SCAN_VIEWPORTS (2)
- OBSERVE_SCREENSHOT_MODE (on_demand|always; по умолчанию on_demand)
- HIDE_OVERLAY (false)
- VIEWPORT_WIDTH/HEIGHT, SYNC_VIEWPORT_WITH_WINDOW (false)
- TYPE_SUBMIT_FALLBACK (true)
- CONSERVATIVE_OBSERVE (false)
- MAX_REOBSERVE_ATTEMPTS (1), MAX_ATTEMPTS_PER_ELEMENT (3), SCROLL_STEP (600)
- MAX_PLANNER_CALLS (20), MAX_NO_PROGRESS_STEPS (20)
- INTERACTIVE_PROMPTS (false)
- Переопределения путей: USER_DATA_DIR, SCREENSHOTS_DIR, STATE_DIR, LOGS_DIR
- Security списки: SENSITIVE_PATHS, RISKY_DOMAINS
- USE_LANGGRAPH (включить граф; по умолчанию включён)

Справка по параметрам (коротко)
-------------------------------
Env / .env:
- `OPENAI_API_KEY` (обязателен), `OPENAI_MODEL` (gpt-4o-mini по умолчанию), `OPENAI_BASE_URL`
- `START_URL` (about:blank), `HEADLESS` (true|false)
- `MAPPING_LIMIT` (int)
- `PLANNER_SCREENSHOT_MODE` (auto|always|never; по умолчанию auto)
- `OBSERVE_SCREENSHOT_MODE` (on_demand|always; по умолчанию on_demand)
- Бюджеты/таймауты: `MAX_STEPS`, `PLANNER_TIMEOUT_SEC`, `EXECUTE_TIMEOUT_SEC`, `MAX_PLANNER_CALLS`, `MAX_NO_PROGRESS_STEPS`
- Луп: `LOOP_REPEAT_THRESHOLD`, `STAGNATION_THRESHOLD`, `MAX_AUTO_SCROLLS`, `LOOP_RETRY_MAPPING_BOOST`, `PAGED_SCAN_STEPS`, `PAGED_SCAN_VIEWPORTS`, `CONSERVATIVE_OBSERVE` (true|false)
- Safety/UX: `AUTO_CONFIRM` (true|false), `INTERACTIVE_PROMPTS` (true|false), `PROGRESS_KEYWORDS`, `AUTO_DONE_MODE` (ask|auto), `AUTO_DONE_THRESHOLD` (int), `AUTO_DONE_REQUIRE_URL_CHANGE` (true|false)
- Устойчивость исполнения: `MAX_REOBSERVE_ATTEMPTS`, `MAX_ATTEMPTS_PER_ELEMENT`, `SCROLL_STEP`, `TYPE_SUBMIT_FALLBACK` (true|false)
- Overlay/viewport: `HIDE_OVERLAY` (true|false), `VIEWPORT_WIDTH/HEIGHT` (ints), `SYNC_VIEWPORT_WITH_WINDOW` (true|false)
- Пути: `USER_DATA_DIR`, `SCREENSHOTS_DIR`, `STATE_DIR`, `LOGS_DIR`
- Security: `SENSITIVE_PATHS`, `RISKY_DOMAINS`

CLI-флаги (override env)
------------------------
- `--goal` / `--goals` (очередь целей)
- `--plan-only` (отключить исполнение; по умолчанию включено)
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

Справка по CLI (коротко):
- `--goal`/`--goals` задают цели
- `--plan-only` отключает действия (режим планирования)
- `--auto-confirm` пропускает подтверждение безопасности
- Время/бюджеты: `--max-steps`, `--planner-timeout`, `--execute-timeout`, `--max-planner-calls`, `--max-no-progress-steps`
- Mapping/loop: `--mapping-limit`, `--loop-repeat-threshold`, `--stagnation-threshold`, `--max-auto-scrolls`, `--loop-retry-mapping-boost`, `--paged-scan-steps`, `--paged-scan-viewports`, `--conservative-observe`
- Скриншоты/overlay: `--screenshot-mode` (planner), `--observe-screenshot-mode` (observe), `--hide-overlay`
- Auto-done: `--auto-done-mode`, `--auto-done-threshold`, `--auto-done-require-url-change`
- Viewport/scroll: `--sync-viewport`/`--no-sync-viewport`, `--scroll-step`, `--max-reobserve-attempts`, `--max-attempts-per-element`
- Workflow: `--clean-between-goals`, `--ui-shell`, `--ui-step-limit`
