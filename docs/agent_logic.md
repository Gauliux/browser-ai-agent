Agent Logic
===========

Stages (FSM)
------------
- orient → context → locate → verify → done (monotonic promotion via goal_check).
- goal_kind: object | list | action (from goal text) influences artifact detection.
- Task mode: find/browse/answer/download (from goal) influences planner prompt (explore_mode, allowed actions).

Terminals
---------
- goal_satisfied — artifact detected (per goal_kind/stage).
- goal_failed — insufficient_knowledge (no_progress/planner_calls/stage_not_advanced) or other failures.
- loop_stuck — world frozen (URL/DOM/candidates) and budget exhausted (repeat/stagnation/auto_scrolls and/or no_progress budget).
- budget_exhausted — max_steps or recursion_limit.
Terminal metadata logged as terminal_reason/type; stop_reason preserved.

LangGraph Flow
--------------
1) observe: capture mapping (overlay optional), zone balancing, optional retries for sparse listings, store hashes (mapping, candidates), loop trigger via repeat/stagnation.
2) loop_mitigation: optional conservative pass; paged_scan with mapping_boost until max_auto_scrolls.
3) goal_check: artifact detection, stage promotion, terminals (goal_satisfied/failed/loop_stuck/budget_exhausted), page_type classification.
4) planner: LLM call with strict schema; context includes goal/stage, page_type, listing_detected, explore_mode, avoid_search, search_no_change, allowed_actions, candidates, errors, loop flags, attempts. Disallowed actions (incl. meta on early stages) → planner_disallowed_action → error_retry.
5) safety: heuristics check, potential confirmation.
6) confirm: prompt/auto-confirm for destructive actions.
7) execute: executes action with fallbacks, per-element limits, TargetClosed retry, updates state_change (URL/DOM), avoid list. Meta actions blocked on early stages.
8) progress: progress score/evidence; auto_done if allowed; ask_user (interactive if enabled, else terminal) only on later stages; repeat/no_progress counters updated.
9) ask_user: interactive confirmation if enabled; non-interactive records stop_reason without blocking.
10) error_retry: one retry after planner/execute errors/timeouts/disallowed action.

Observation & Mapping
---------------------
- Set-of-Mark JS annotates interactive elements, adds data-agent-id, captures tag/text/role/zone/bbox/fixed/nav/disabled/attr name/id/aria.
- Zone balancing (top/mid/bottom), nav/fixed deprioritized, goal-aware candidate extraction.
- Optional overlay badges (hidden via flag), optional viewport sync, optional screenshot (observe_screenshot_mode).

Planning
--------
- Action schema: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user.
- Context: mapping (capped/dynamic), recent obs, loop/error/attempts, avoid_elements, allowed_actions, explore/listing flags, search_controls, state_change_hint, candidates.
- Validation: jsonschema; disallowed actions by stage rejected to error_retry.

Execution
---------
- Actions mapped to Playwright: navigate/goto, search via keyboard (or Ctrl+L fallback), history nav, scroll, click/type (fill), screenshot.
- Fallbacks: reobserve with alternating scroll → JS click → text-match click; per-element fail counts to avoid.
- Artifacts: exec JSON and screenshots labeled with session/step.

Loop/No-progress Handling
-------------------------
- repeat_count (action+element+URL), stagnation_count (mapping hash), auto_scrolls_used, no_progress_steps, planner_calls.
- world_frozen check (URL/DOM/candidate hashes) gates loop_stuck.
- loop_mitigation adds paged_scan + mapping boost; conservative observe option.

Progress & Stopping
-------------------
- progress score: url/title/keywords/goal_hits/last_action target; page_type heuristic (listing/detail).
- auto_done only on later stages; ask_user gated by stage and INTERACTIVE_PROMPTS.
- Terminals enforced: every run ends with terminal_reason/type logged.
