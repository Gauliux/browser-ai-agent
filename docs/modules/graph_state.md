Module: src/agent/core/graph_state.py
=====================================

Responsibility
--------------
- Defines GraphState (TypedDict) and shared helpers for the graph.

Highlights
----------
- GraphState fields: goal/goal_kind/goal_stage, task_mode, observation/prev_observation, hashes (mapping/candidate), planner_result, security_decision, exec_result, loop counters, no_progress/progress counters, planner_calls, auto_scrolls, avoid_elements, visited_urls/elements, exec_fail_counts, records, recent_observations, tabs/tab_events/active_tab_id, context_events, intent_text/history, ux_messages, action_history, stop_reason/details, terminal_reason/type.
- Constants: STOP_TO_TERMINAL mapping, TERMINAL_TYPES, INTERACTIVE_PROMPTS.
- Helpers: goal_tokens, goal_url_token, classify_task_mode/kind, page_type_from_scores, progress_score, goal_is_find_only, mapping_hash/candidate_hash/extract_candidates, add_record, stage_* helpers, pick_committed_action, commit scoring.

Used By
-------
- All node_* and planner/execute helpers; langgraph_loop for initial_state; termination_normalizer for terminal mapping.
