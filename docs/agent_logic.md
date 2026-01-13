Agent Logic
===========

Stages (FSM)
------------
- orient → context → locate → verify → done (monotonic; goal_stage/goal_kind are fixed).
- goal_kind: object | list | action; task_mode (find/browse/answer/download) only tweaks planner hints (explore_mode, allowed_actions), not the FSM.

Terminals
---------
- goal_satisfied, goal_failed (insufficient_knowledge/stage_not_advanced/budgets), loop_stuck, budget_exhausted. The set is fixed; terminal_reason/type are normalized on exit.

Graph Flow
----------
1) observe: capture Observation (Set-of-Mark); overlay optional; goal-aware candidate pickup for sparse listings; mapping_hash/candidate_hash; loop_trigger via repeat/stagnation; records tabs metadata, active_tab_id, tab_events, context_events.
2) loop_mitigation: conservative_pass (if enabled) and paged_scan with mapping_boost up to max_auto_scrolls.
3) goal_check: artifact detection and stage promotion; terminals (goal_satisfied/failed/loop_stuck/budget_exhausted); page_type classification.
4) planner: builds context (goal/stage/kind, page_type, listing_detected, explore_mode, allowed_actions incl. switch_tab, avoid_search/search_no_change, candidates with is_disabled, search_controls, state_change_hint, loop/error/attempts, tabs/active_tab_id); calls planner.plan with timeout; planner_disallowed_action → error_retry.
5) safety: analyze_action (including navigate/search/go_back/go_forward) for risk; may require confirm.
6) confirm: prompt/auto_confirm for risky actions.
7) execute: runs action with fallbacks (reobserve + scroll wiggle → JS click → text-match); handles switch_tab, context events (url_changed/dom_changed/tab open), updates visited/avoid/attempts; saves records and UX.
8) progress: computes score/evidence, page_type, auto_done (by stage/settings); ask_user only on later stages; updates repeat/no_progress/planner_calls/step counters.
9) ask_user: interactive only if INTERACTIVE_PROMPTS; otherwise immediately writes stop_reason.
10) error_retry: single retry after planner/execute errors/timeouts/disallowed.

Observation & Mapping
---------------------
- JS Set-of-Mark: tag/text/role/zone/bbox/fixed/nav/is_disabled/attr_name/id/aria; data-agent-id; overlay badges optional.
- Zone balancing; goal-aware candidate extraction; optional viewport sync; screenshots controlled by observe_screenshot_mode.

Planning
--------
- Actions: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user.
- Context includes recent observations, loop/error/attempts, avoid_elements, candidates (with is_disabled), tabs/active_tab_id and tab events, intent_text/history (UX-only), state_change_hint, progress/no-progress.
- Validation: jsonschema; meta-actions limited by stage as in code.

Execution
---------
- Executes all actions, including switch_tab as first-class (not a failure); navigation/search/history/scroll, click/type, screenshot.
- Fallbacks: reobserve + scroll wiggle, JS click, text-match click; per-element fail counts → avoid_elements.
- Context events: url_changed/dom_changed, tab open/activate; intent logged to intent_history; UX via append_ux.

Loop/No-progress Handling
-------------------------
- repeat_count (action+element+URL), stagnation_count (mapping hash), auto_scrolls_used, no_progress_steps, planner_calls.
- world_frozen (URL/DOM/candidate hashes) for loop_stuck; loop_mitigation adds paged_scan + conservative observe.

Progress & Stopping
-------------------
- progress_score: url/title/keywords/goal_hits/last_action target; page_type heuristic (listing/detail).
- auto_done works only on late stages; ask_user/interactive optional.
- Every run ends with terminal_reason/type; recursion_limit guards infinite loops.
