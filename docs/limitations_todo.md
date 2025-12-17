Limitations and TODOs
=====================

Known Limitations
-----------------
- Нет эвристик выбора вкладки: активная вкладка меняется только при явном switch_tab/новой вкладке от браузера.
- Page types limited to listing/detail heuristic; no explicit HOME/SEARCH_FORM classification.
- Legacy loop (src/agent/legacy/loop.py) retained but not maintained.
- No mock/test harness for quick regression; no automated tests.
- UI shell prompts not localized for new terminal reasons.
- Planner allowed_actions enforcement is stage-based but not semantic beyond current heuristics.
- Token strategy: role/title-aware sorting (по токенам заголовка страницы) и dynamic limits; goal-aware используются только для списка кандидатов, CV нет.

Future Improvements (potential)
-------------------------------
- Add auto tab selection heuristics and planner support for multi-tab workflows.
- Expand page type classification and planner hints (home/search-form).
- Build mock page and smoke test script for observe→plan→execute regression.
- Improve summaries/UX (UI shell messages, quiet/verbose flags).
- Adaptive token economy (screenshot on doubt/error more systematically, role/goal-aware sampling).
- Richer safety/reporting (structured terminal summaries).
