Module: src/agent/core/graph_state.py
=====================================

Responsibility
--------------
- Определяет GraphState (TypedDict) и общие хелперы для графа.

Highlights
----------
- GraphState поля: goal/goal_kind/goal_stage, task_mode, observation/prev, hashes (mapping/candidate), planner_result, security_decision, exec_result, loop counters, no_progress/progress counters, planner_calls, auto_scrolls, avoid_elements, visited_urls/elements, exec_fail_counts, records, recent_observations, tabs/tab_events/active_tab_id, context_events, intent_text/history, ux_messages, action_history, stop_reason/details, terminal_reason/type.
- Константы: STOP_TO_TERMINAL маппинг, TERMINAL_TYPES, INTERACTIVE_PROMPTS.
- Хелперы: goal_tokens, goal_url_token, classify_task_mode/kind, page_type_from_scores, progress_score, goal_is_find_only, mapping_hash/candidate_hash/extract_candidates, add_record, stage_* helpers, pick_committed_action, commit scoring.

Used By
-------
- Все node_* и планер/execute helpers; langgraph_loop для initial_state; termination_normalizer для terminal mapping.
