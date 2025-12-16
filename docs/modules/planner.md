Module: src/agent/planner.py
============================

Responsibility
--------------
- Call OpenAI (AsyncOpenAI) with strict function-calling schema to decide next browser action.
- Build prompt with structured context (goal, observations, mapping, loop/error/attempts, page signals).
- Validate and persist raw responses (optional).

Action Schema
-------------
- tool: "browser_action"
- action: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user
- element_id: int|null
- value: string|null
- requires_confirmation: bool

Key Behavior
------------
- _format_observation: serialize observation with capped mapping, zone round-robin, title-token scoring (из текста страницы) для ordering; trims text.
- _recent_context_text: last observations summary (up to 3).
- _goal_tokens_from_title: extract tokens for scoring.
- plan(...):
  - Retries with backoff on rate limit; jsonschema validation; raw logging to state_dir if enabled.
  - Parameters include goal, observation, recent_observations, include_screenshot, mapping_limit, loop flags, avoid_elements, error/progress/actions context, listing_detected, explore_mode, avoid_search/search_no_change, page_type, task_mode, avoid_actions, candidate_elements, search_controls, state_change_hint, allowed_actions.
  - If observation lacks screenshot and include_screenshot true, recapture handled by caller; planner just accepts observation.
- _plan_once: builds system/user messages, optional image (base64); enforces tool_choice; sanitizes missing fields; raises on missing tool call.

Settings Used
-------------
- model/base_url from Planner init; mapping_limit passed in; raw_log_dir if ENABLE_RAW_LOGS.

Integration Points
------------------
- langgraph_loop planner_node assembles context, mapping_limit, allowed_actions, loop/error/attempts signals.
- load_recent_observations: helper to load last N observation JSONs from state_dir (not used in LangGraph loop directly).
