Module: src/agent/langgraph_loop.py
===================================

Responsibility
--------------
- Thin facade over LangGraph: assembles nodes (core/node_*.py), compiles the graph via graph_orchestrator, sets initial GraphState, runs with recursion_limit, and normalizes the terminal.

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
- intent_text and intent_history; ux_messages (UX narration log).
- records (steps with artifact paths), recent_observations window.

Terminals & FSM
---------------
- Terminal reasons are fixed: goal_satisfied, goal_failed, loop_stuck, budget_exhausted (normalized in termination_normalizer).
- Stages are monotonic; meta-actions are available only on later stages (per code).

Nodes (split across core/node_*.py)
-----------------------------------
- observe: capture observation (Set-of-Mark), overlay optional, goal-aware retries for sparse listings; hashes/candidates; loop_trigger; records tabs/active_tab_id/tab_events/context_events.
- loop_mitigation: conservative pass (optional), paged_scan with mapping_boost up to max_auto_scrolls.
- goal_check: stage promotion, artifact detection, terminals (goal_satisfied/failed/loop_stuck/budget_exhausted), page_type classification.
- planner: builds context (goal/stage, page_type, listing_detected, explore_mode, allowed_actions incl. switch_tab, avoid_search/search_no_change, candidates with is_disabled, search_controls, state_change_hint, loop/error/attempts, tabs/active_tab_id), calls planner with timeout; disallowed/timeout/error → error_retry.
- safety: analyze_action.
- confirm: prompt/auto_confirm when required.
- execute: executes action (incl. switch_tab) with fallbacks, records context events and UX, updates visited/avoid/fail counts, saves records.
- progress: computes score/evidence/page_type, auto_done/ask_user by stage/settings, updates repeat/no_progress/planner_calls/step counters.
- ask_user: interactive only if INTERACTIVE_PROMPTS; otherwise immediately writes stop_reason.
- error_retry: single retry after planner/execute errors/timeouts/disallowed.

Flow Edges
----------
- START → observe → (loop_mitigation if loop_trigger) → goal_check → planner → safety → confirm → execute → progress → ask_user → observe/END.
- error_retry after planner/execute errors/timeouts/disallowed; END on any stop_reason.

Settings Impact
---------------
- max_steps → recursion_limit (max(max_steps+20, 50)); loop thresholds; paged_scan_*; conservative_observe; auto_done_*; max_planner_calls; max_no_progress_steps; timeouts; mapping_limit/boost; progress_keywords; INTERACTIVE_PROMPTS; headless/viewport/screenshot_modes; scroll_step; max_attempts_per_element; max_reobserve_attempts; hide_overlay.

Artifacts/Logging
-----------------
- TextLogger/TraceLogger (infra/tracing) for records and summary.
- Files in data/state (planner_raw_path, exec_result_path) + screenshots; UX messages stored in ux_messages (UX layer only).
