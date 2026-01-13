Module: src/agent/core/planner.py
=================================

Responsibility
--------------
- OpenAI function-calling planner (AsyncOpenAI) with strict schema.
- Builds prompt from observations, candidates, tabs, loop/error signals, page context.
- Validates/logs raw responses (when ENABLE_RAW_LOGS).

Action Schema
-------------
- tool: "browser_action"
- action: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user
- element_id: int|null
- value: string|null
- requires_confirmation: bool

Key Behavior
------------
- _format_observation: serialize Observation with capped mapping, goal-aware ordering (title/context aware), trims text; keeps is_disabled.
- plan(...):
  - retries/backoff on rate limit, jsonschema validation, raw logging to state_dir.
  - Context: goal, observation, recent_observations, include_screenshot, mapping_limit, loop flags,
    avoid_elements, errors/progress/actions, listing_detected, explore_mode, avoid_search/search_no_change,
    page_type, task_mode, avoid_actions, candidate_elements, search_controls, state_change_hint,
    allowed_actions, tabs/active_tab_id.
- _plan_once: builds system/user messages, optional image base64; tool_choice enforced; sanitizes missing fields.

Settings Used
-------------
- model/base_url from Planner init; mapping_limit passed in; raw_log_dir when ENABLE_RAW_LOGS.

Integration Points
------------------
- node_planner builds context and passes to plan(), including candidates with is_disabled and tabs.
