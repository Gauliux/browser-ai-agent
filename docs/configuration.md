Configuration and Parameters
============================

Environment Variables (defaults) — подробно
-------------------------------------------
- OPENAI_API_KEY — ключ для вызова LLM; без него агент не планирует (только открывает браузер).
- OPENAI_MODEL=gpt-4o-mini — модель для планера.
- OPENAI_BASE_URL — кастомный endpoint, если нужен.
- START_URL=about:blank - стартовая страница при запуске runtime.
- HEADLESS=false — если true, браузер без UI (обычно держим false для наблюдения).
- MAPPING_LIMIT=30 — базовый лимит элементов, отправляемых планеру; влияет на размер контекста и токены.
- PLANNER_SCREENSHOT_MODE=auto (auto|always|never) — включает/выключает передачу скрина в планер.
- MAX_STEPS=6 — верхний бюджет шагов; при достижении → budget_exhausted.
- PLANNER_TIMEOUT_SEC=25 — таймаут LLM-вызова; timeout → planner_timeout → error_retry/stop.
- EXECUTE_TIMEOUT_SEC=20 — таймаут исполнения действия; timeout → execute_timeout → error_retry/stop.
- AUTO_CONFIRM=false — если true, пропускает подтверждение потенциально опасных действий.
- ENABLE_RAW_LOGS=true — сохранять сырые planner ответы в state_dir.
- LOOP_REPEAT_THRESHOLD=2 — порог повторов для детекции loop.
- STAGNATION_THRESHOLD=2 — порог стагнации по mapping hash.
- MAX_AUTO_SCROLLS=3 — лимит paged_scan при loop_mitigation.
- LOOP_RETRY_MAPPING_BOOST=20 — бонус к mapping_limit при лупе/ошибке.
- PROGRESS_KEYWORDS="cart,корзина,..." — ключевые слова для прогресс-оценки.
- AUTO_DONE_MODE=ask (ask|auto) — авто-остановка или запрос при уверенности.
- AUTO_DONE_THRESHOLD=2 — порог прогресса для auto_done/ask_user.
- AUTO_DONE_REQUIRE_URL_CHANGE=true — требовать смену URL для авто done (можно выключить).
- PAGED_SCAN_STEPS=2 — сколько шагов paged_scan при loop_mitigation.
- PAGED_SCAN_VIEWPORTS=2 — сколько viewport-сканов за шаг paged_scan.
- OBSERVE_SCREENSHOT_MODE=on_demand (on_demand|always) — скрины в observe.
- HIDE_OVERLAY=false — скрыть/показать числовые бейджи.
- VIEWPORT_WIDTH/HEIGHT — задать фиксированный viewport.
- SYNC_VIEWPORT_WITH_WINDOW=false — если true, подгоняет viewport к окну.
- TYPE_SUBMIT_FALLBACK=true — после type жмёт Enter (best-effort).
- CONSERVATIVE_OBSERVE=false — при loop сначала делает аккуратное observe без скролла.
- MAX_REOBSERVE_ATTEMPTS=1 — сколько reobserve ретраев в execute fallbacks.
- MAX_ATTEMPTS_PER_ELEMENT=3 — после стольких фейлов элемент попадает в avoid.
- SCROLL_STEP=600 — шаг скролла для scroll и reobserve wiggle.
- MAX_PLANNER_CALLS=20 — бюджет LLM вызовов; превышение → goal_failed.
- MAX_NO_PROGRESS_STEPS=20 — бюджет шагов без прогресса; превышение → goal_failed.
- INTERACTIVE_PROMPTS=false — если true, progress/ask_user блокируют и спрашивают; иначе без ожидания.
- Path overrides: USER_DATA_DIR, SCREENSHOTS_DIR, STATE_DIR, LOGS_DIR - расположение профиля/артефактов/логов.
- Security lists: SENSITIVE_PATHS, RISKY_DOMAINS — строки через запятую; навигация на них требует confirm.
- EXECUTE (не основной, но читается) — включает исполнение в legacy контексте; в CLI есть --execute.
- USE_LANGGRAPH (опционально) — включает LangGraph по env.

CLI Flags (override env) - подробно
-----------------------------------
- --goal / --goals — задать одну или несколько целей (очередь).
- --execute — включить выполнение действий (иначе только планер; для LangGraph обычно включаем).
- --auto-confirm — автоматически подтверждать рискованные действия.
- --max-steps, --planner-timeout, --execute-timeout — бюджеты/таймауты.
- --screenshot-mode — для планера (auto/always/never).
- --mapping-limit — ограничение элементов для планера.
- --loop-repeat-threshold, --stagnation-threshold, --max-auto-scrolls, --loop-retry-mapping-boost — параметры анти-лупа/mitigation.
- --langgraph — выбрать LangGraph оркестратор.
- --hide-overlay — скрыть бейджи в DOM.
- --paged-scan-steps, --paged-scan-viewports — глубина paged_scan.
- --auto-done-mode, --auto-done-threshold, --auto-done-require-url-change — поведение авто-остановки.
- --observe-screenshot-mode — on_demand|always для observe.
- --sync-viewport / --no-sync-viewport — подгонять viewport к окну или нет.
- --clean-between-goals — очистить logs/state/screenshots между целями (профиль остаётся).
- --ui-shell — запустить UI shell (интерактивный супервизор); --ui-step-limit — отдельный лимит шагов для UI shell.
- --conservative-observe — включить аккуратный проход перед скроллом при лупе.
- --max-reobserve-attempts — лимит реобсерваций в execute fallbacks.
- --max-attempts-per-element — сколько фейлов до avoid.
- --scroll-step - шаг скролла (переопределяет env).

Priority
--------
- CLI overrides → .env в корне репозитория → переменные окружения процесса. .env загружается с override=True, чтобы не пропускать значения из файла.

Что влияет на что (кратко)
--------------------------
- INTERACTIVE_PROMPTS: on → блокирующие вопросы (ask_user/progress), off (default) → без ожидания.
- auto_confirm: пропускает confirm на рискованных действиях.
- mapping_limit (+ loop boost): сколько элементов видит LLM → объём токенов/контекст.
- max_steps / max_planner_calls / max_no_progress_steps: бюджеты → терминалы goal_failed/budget_exhausted.
- loop thresholds + paged_scan: когда включается loop_mitigation и сколько сканов сделает.
- max_reobserve_attempts / max_attempts_per_element: устойчивость execute, рост avoid-листа.
- scroll_step: величина скролла в действиях и фолбэках.
- hide_overlay: видимость бейджей; id остаются.
- screenshot modes: частота скринов в observe/planner.
- Path overrides: куда пишутся артефакты/логи/профиль.
