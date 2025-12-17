Module: src/agent/core/planner.py
=================================

Responsibility
--------------
- OpenAI function-calling planner (AsyncOpenAI) with strict schema.
- Строит промпт на основе наблюдений, кандидатов, вкладок, loop/error и сигналов страницы.
- Валидирует/логирует сырые ответы (если ENABLE_RAW_LOGS).

Action Schema
-------------
- tool: "browser_action"
- action: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user
- element_id: int|null
- value: string|null
- requires_confirmation: bool

Key Behavior
------------
- _format_observation: сериализация Observation с capped mapping, goal-aware ordering (с учетом page title/context), trims text; сохраняет is_disabled.
- plan(...):
  - retries/backoff при rate limit, jsonschema validation, raw logging в state_dir.
  - Контекст: goal, observation, recent_observations, include_screenshot, mapping_limit, loop flags,
    avoid_elements, errors/progress/actions, listing_detected, explore_mode, avoid_search/search_no_change,
    page_type, task_mode, avoid_actions, candidate_elements, search_controls, state_change_hint,
    allowed_actions, tabs/active_tab_id.
- _plan_once: строит system/user, optional image base64; tool_choice enforced; sanitizes missing fields.

Settings Used
-------------
- model/base_url из Planner init; mapping_limit извне; raw_log_dir при ENABLE_RAW_LOGS.

Integration Points
------------------
- node_planner собирает контекст и передаёт в plan(), включая candidates с is_disabled и табы.
