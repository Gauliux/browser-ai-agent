Module: src/agent/langgraph_loop.py
===================================

Responsibility
--------------
- Define and run the LangGraph state graph for the agent loop.
- Manage FSM stages, terminals, loop mitigation, planner/execution/error handling, progress, and user prompts.

State (GraphState highlights)
-----------------------------
- goal, goal_kind, goal_stage (orient/context/locate/verify/done), task_mode.
- observation, prev_observation, recent_observations, mapping_hash, candidate_hash.
- planner_result, security_decision, exec_result.
- stop_reason/details, terminal_reason/type.
- loop tracking: repeat_count, stagnation_count, auto_scrolls_used, loop_trigger, loop_trigger_sig.
- progress/no-progress: last_progress_score/evidence, no_progress_steps, progress_steps.
- budgets: planner_calls, max_* from settings.
- action_history, avoid_elements, visited_urls/elements, exec_fail_counts.
- last_state_change (url_changed/dom_changed), last_action_no_effect, loop_mitigated, conservative_probe_done, error_retries.
- candidate_elements, artifact_detected/type, page_type, avoid_actions.

Terminals & FSM
---------------
- Terminal reasons: goal_satisfied, goal_failed, loop_stuck, budget_exhausted (normalized at run end).
- Stages monotonic (promoted in goal_check). Meta actions allowed only locate/verify; disallowed otherwise.
- ask_user/progress prompts gated by stage and INTERACTIVE_PROMPTS.

Nodes (simplified)
------------------
- observe: capture observation (overlay optional), handle switch_tab hint, sparse listing retries, set hashes/candidates, detect loop trigger (repeat/stagnation), optional quick goal_satisfied check for object detail.
- loop_mitigation: conservative pass (optional), paged_scan with mapping boost until max_auto_scrolls.
- goal_check: stage promotion, artifact detection (by goal_kind and page_type), terminals (goal_satisfied/failed/loop_stuck/budget_exhausted). loop_stuck uses world_frozen (URL/DOM/candidates) + budget counters. insufficient_knowledge triggers if stage not advanced after budget.
- planner: build context (page_type, listing_detected, explore_mode, allowed_actions, avoid_search/search_no_change, candidates, search_controls, state_change_hint, loop/error/attempts), call planner.plan with timeout; disallowed actions → planner_disallowed_action; error_retry on timeout/error/disallowed.
- safety: analyze_action.
- confirm: prompt/auto_confirm if required.
- execute: run execute_with_fallbacks; meta actions blocked on early stages; save exec result; track visited/avoid/fail counts; compute state_change hashes; append records.
- progress: compute score/evidence, page_type; auto_done if allowed; ask_user only on later stages; update repeat/no_progress counters and step.
- ask_user: non-interactive (default) logs decision without blocking; interactive prompt if INTERACTIVE_PROMPTS true.
- error_retry: one retry clears stop_reason to re-enter observe.

Flow Edges
----------
- START → observe → (loop_mitigation if loop) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.
- error_retry reroutes from planner/execute errors/timeouts/disallowed; END on stop_reason.

Settings Impact
---------------
- max_steps → budget_exhausted; loop thresholds; max_planner_calls/max_no_progress_steps; max_attempts_per_element; max_reobserve_attempts; mapping_limit/mapping_boost; paged_scan_*; INTERACTIVE_PROMPTS; auto_confirm; timeouts; hide_overlay/observe_screenshot_mode; auto_done_*; scroll_step; conservative_observe; loop_retry_mapping_boost.

Artifacts/Logging
-----------------
- Uses tracing TextLogger/TraceLogger for records and summary; records include paths (planner_raw_path, exec_result_path), attempts, loop triggers.
- Filenames include session/step labels passed down to observe/execute.
