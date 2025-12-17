Repository Structure
====================

Top-level
---------
- src/main.py - CLI entrypoint, запускает LangGraph граф или legacy loop (legacy заморожен).
- src/agent/core - узлы графа, graph_state/orchestrator, базовые observe/planner/execute/security.
- src/agent/infra - runtime, capture, tracing, paths, termination_normalizer.
- src/agent/io - ui_shell и UX-narration.
- src/agent/config - загрузка Settings (.env/env/CLI) и Paths.
- src/agent/legacy - старый цикл/state (оставлен для совместимости).
- docs/ - документация.
- data/ - user_data (браузер профиль), screenshots, state artifacts (создаются при запуске).
- logs/ - agent.log, trace.jsonl (создаются при запуске).

Key Module Responsibilities
---------------------------
- config/config.py - загрузка настроек (приоритет CLI -> .env -> env), clamp значений, Paths init.
- infra/paths.py - резолв каталогов (env overrides), ensure dirs.
- infra/runtime.py - Playwright headful persistent browser, активная вкладка, TargetClosed устойчивость, выбор страницы.
- infra/capture.py - observe-проход с ретраями, paged_scan.
- infra/tracing.py - Text/JSONL логгеры, step id.
- infra/termination_normalizer.py - нормализация терминалов LangGraph.
- core/graph_state.py - GraphState TypedDict + хелперы (hashes, scoring, classifiers, records).
- core/graph_orchestrator.py - сборка графа узлов.
- core/node_*.py - узлы observe/loop_mitigation/goal_check/planner/safety/confirm/execute/progress/ask_user/error_retry.
- core/observe.py / planner.py / execute.py / security.py - функциональные блоки узлов.
- io/ui_shell.py - опциональный интерактивный супервизор; io/ux_narration.py - UX-лог.
- langgraph_loop.py - тонкий фасад: собирает узлы/граф, запускает с recursion_limit, нормализует терминал.
- legacy/loop.py, legacy/state.py - старый цикл/state (не развиваются).
- main.py - CLI/flags/env overrides, runtime startup, goal queue, выбор LangGraph/legacy/UI shell.

Artifacts/Logs
--------------
- data/state - observation/planner/execute JSONs (по сессиям/шагам).
- data/screenshots - observe/exec скрины (session/step в имени).
- logs/agent.log - текстовый лог.
- logs/trace.jsonl - структурный трейс (если включён).
- data/user_data - persistent browser profile.
