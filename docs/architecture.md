Architecture Overview
=====================

Goal
----
Headful, persistent Playwright агент, оркестрируемый LangGraph: наблюдает DOM (Set-of-Mark), планирует через OpenAI function-calling, исполняет действия с фолбэками и безопасностью, фиксирует вкладки/контекстные события/интент/UX-нарратив.

Key Decisions
-------------
- Стек: Python 3, Playwright headful persistent, OpenAI SDK (f-calling), LangGraph.
- Ориентация на наблюдение: Set-of-Mark вместо CV; лимит/баланс элементов; скрин по запросу.
- Оркестрация: явный граф узлов observe → loop_mitigation → goal_check → planner → safety → confirm → execute → progress → ask_user/error_retry; структура не меняется.
- Безопасность: эвристики для risk actions + confirm (auto_confirm опционален).
- Стабильные FSM/терминалы: stages orient/context/locate/verify/done, terminal_reason fixed (goal_satisfied/goal_failed/loop_stuck/budget_exhausted).
- Прозрачность: intent_text/history, UX-narration, trace.jsonl, records.

Main Components
---------------
- Runtime (infra/runtime.py): жизненный цикл браузера, активная вкладка, TargetClosed устойчивость, метаданные вкладок.
- Capture (infra/capture.py): observe с ретраями и paged_scan.
- Graph (core/graph_orchestrator.py + node_*.py): узлы графа разнесены по файлам; тонкий фасад langgraph_loop.py собирает и запускает.
- State/helpers (core/graph_state.py): GraphState TypedDict, hashes, classifiers (goal/page/task), scoring, records, terminal маппинг.
- Planner (core/planner.py + node_planner): LLM с строгой схемой и богатыми контекстами.
- Execute (core/execute.py + node_execute): исполнение действий с фолбэками, учёт вкладок, контекстных событий.
- Observe (core/observe.py + node_observe): Set-of-Mark JS, overlay, goal-aware retries для sparse listings.
- Safety/confirm (core/security.py + node_safety/confirm): риск-оценка + подтверждения.
- Progress (node_progress): прогресс-скоринг, авто done/ask_user, no-progress счётчики.
- UX (io/ux_narration.py, io/ui_shell.py): поток сообщений для пользователя, опциональный интерактивный шелл.

Flows
-----
- LangGraph: observe → (loop_mitigation если loop_trigger) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END; error_retry после planner/execute ошибок/таймаутов/disallowed.
- Терминалы нормализуются termination_normalizer к terminal_reason/type.
- Начальное состояние выставляет goal_kind/stage, счётчики, tabs/tab_events, intent/ux/context_events.

State Tracing/Artifacts
-----------------------
- data/state: planner/execute JSON, labels session/step; observe mapping/screenshot пути.
- logs/trace.jsonl: записи узлов/records/summary.
- logs/agent.log: текстовые события.
- UX messages и intent_history сохраняются в GraphState (для отчётов, не для логики).
