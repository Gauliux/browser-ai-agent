Module: src/agent/langgraph_loop.py
===================================

Responsibility
--------------
- Тонкий фасад над LangGraph: собирает узлы (core/node_*.py), компилирует граф через graph_orchestrator, выставляет начальное GraphState, запускает с recursion_limit и нормализует терминал.

State (GraphState highlights)
-----------------------------
- goal, goal_kind, goal_stage (orient/context/locate/verify/done), task_mode.
- observation, prev_observation, recent_observations, mapping_hash, candidate_hash.
- planner_result, security_decision, exec_result.
- stop_reason/details, terminal_reason/type.
- loop tracking: repeat_count, stagnation_count, auto_scrolls_used, loop_trigger, loop_trigger_sig.
- progress/no-progress: last_progress_score/evidence, no_progress_steps, progress_steps, planner_calls.
- action_history, avoid_elements, visited_urls/elements, exec_fail_counts.
- state_change flags: url_changed/dom_changed, loop_mitigated, conservative_probe_done, error_retries.
- tabs metadata: tabs list, tab_events, active_tab_id; context_events (URL/DOM/tab changes).
- intent_text и intent_history; ux_messages (UX narration log).
- records (шаги с путями artifacts), recent_observations window.

Terminals & FSM
---------------
- Terminal reasons фиксированы: goal_satisfied, goal_failed, loop_stuck, budget_exhausted (нормализуются в termination_normalizer).
- Стадии монотонны, meta-actions доступны только на поздних стадиях (как в коде).

Nodes (разнесены по файлам core/node_*.py)
------------------------------------------
- observe: capture observation (Set-of-Mark), overlay optional, goal-aware retries для sparse listings; hashes/candidates; loop_trigger; фиксирует табы/active_tab_id/tab_events/context_events.
- loop_mitigation: conservative pass (опционально), paged_scan с mapping_boost до max_auto_scrolls.
- goal_check: stage promotion, artifact detection, terminals (goal_satisfied/failed/loop_stuck/budget_exhausted), page_type классификация.
- planner: строит контекст (goal/stage, page_type, listing_detected, explore_mode, allowed_actions включая switch_tab, avoid_search/search_no_change, candidates с is_disabled, search_controls, state_change_hint, loop/error/attempts, tabs/active_tab_id), вызывает планер с таймаутом; disallowed/timeout/error → error_retry.
- safety: analyze_action.
- confirm: prompt/auto_confirm при необходимости.
- execute: исполняет действие (incl. switch_tab) с фолбэками, фиксирует контекстные события и UX, обновляет visited/avoid/fail counts, сохраняет records.
- progress: считает score/evidence/page_type, auto_done/ask_user по стадиям/настройкам, обновляет счётчики repeat/no_progress/planner_calls/step.
- ask_user: интерактивно только если INTERACTIVE_PROMPTS, иначе мгновенная запись stop_reason.
- error_retry: один повтор после planner/execute ошибок/таймаутов/disallowed.

Flow Edges
----------
- START → observe → (loop_mitigation если loop_trigger) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.
- error_retry после planner/execute ошибок/таймаутов/disallowed; END на любом stop_reason.

Settings Impact
---------------
- max_steps ↔ recursion_limit (max(max_steps+20, 50)), loop thresholds, paged_scan_*, conservative_observe, auto_done_*, max_planner_calls, max_no_progress_steps, timeouts, mapping_limit/boost, progress_keywords, INTERACTIVE_PROMPTS, headless/viewport/screenshot_modes, scroll_step, max_attempts_per_element, max_reobserve_attempts, hide_overlay.

Artifacts/Logging
-----------------
- TextLogger/TraceLogger (infra/tracing) для records и summary.
- Файлы в data/state (planner_raw_path, exec_result_path) + screenshots; UX сообщения пишутся в ux_messages (UX-слой, не влияет на логику).
