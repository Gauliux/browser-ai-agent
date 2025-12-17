Agent Logic
===========

Stages (FSM)
------------
- orient → context → locate → verify → done (монотонно; goal_stage/goal_kind фиксированы).
- goal_kind: object | list | action; task_mode (find/browse/answer/download) влияет на подсказки планеру (explore_mode, allowed_actions), но FSM не меняется.

Terminals
---------
- goal_satisfied, goal_failed (insufficient_knowledge/stage_not_advanced/budgets), loop_stuck, budget_exhausted. Набор фиксирован; terminal_reason/type нормализуются на выходе.

Graph Flow
----------
1) observe: захват Observation (Set-of-Mark), overlay опционален, goal-aware добор элементов для sparse listing; mapping_hash/candidate_hash; loop_trigger через repeat/stagnation; сохраняет tabs метаданные, active_tab_id, tab_events, context_events.
2) loop_mitigation: conservative_pass (если включено) и paged_scan с mapping_boost до max_auto_scrolls.
3) goal_check: артефакт-детекция и stage promotion; terminals (goal_satisfied/failed/loop_stuck/budget_exhausted); page_type классификация.
4) planner: строит контекст (goal/stage/kind, page_type, listing_detected, explore_mode, allowed_actions incl. switch_tab, avoid_search/search_no_change, candidates с is_disabled, search_controls, state_change_hint, loop/error/attempts, tabs/active_tab_id); вызывает planner.plan с таймаутом; planner_disallowed_action → error_retry.
5) safety: analyze_action (включая navigate/search/go_back/go_forward) на риск; может требовать confirm.
6) confirm: prompt/auto_confirm для требующих подтверждения.
7) execute: исполняет действие с фолбэками (reobserve+scroll wiggle → JS click → text-match); учитывает switch_tab, контекстные события (url_changed/dom_changed/tab open), обновляет visited/avoid/attempts; сохраняет records и UX.
8) progress: считает score/evidence, page_type, auto_done (по stage/настройкам), ask_user только на поздних стадиях; обновляет repeat/no_progress/planner_calls/step.
9) ask_user: интерактивно (если INTERACTIVE_PROMPTS) или мгновенная запись stop_reason.
10) error_retry: один повтор после planner/execute ошибок/таймаутов/disallowed.

Observation & Mapping
---------------------
- JS Set-of-Mark: tag/text/role/zone/bbox/fixed/nav/is_disabled/attr_name/id/aria; data-agent-id; overlay номера опциональны.
- Zone балансировка, goal-aware candidate extraction, viewport sync опционален, скрины по observe_screenshot_mode.

Planning
--------
- Actions: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user.
- Контекст включает последние наблюдения, loop/error/attempts, avoid_elements, candidates (с is_disabled), tabs/active_tab_id и tab events, intent_text/history (читается только для UX, не в логике), state_change_hint, progress/no-progress.
- Валидация: jsonschema; мета-действия ограничены ранними стадиями (как было).

Execution
---------
- Отрабатывает все actions, включая switch_tab как first-class (не считается failure); navigation/search/history/scroll, click/type, screenshot.
- Фолбэки: reobserve + scroll wiggle, JS click, text-match click; per-element fail counts → avoid_elements.
- Контекстные события: url_changed/dom_changed, tab open/activate, intent записывается в intent_history, UX-лог append_ux.

Loop/No-progress Handling
-------------------------
- repeat_count (action+element+URL), stagnation_count (mapping hash), auto_scrolls_used, no_progress_steps, planner_calls.
- world_frozen (URL/DOM/candidate hashes) для loop_stuck; loop_mitigation добавляет paged_scan + conservative observe.

Progress & Stopping
-------------------
- progress_score: url/title/keywords/goal_hits/last_action target; page_type heuristic (listing/detail).
- auto_done работает только на поздних стадиях; ask_user/interactive опционален.
- Каждый запуск завершает terminal_reason/type; recursion_limit защищает от бесконечных циклов.
