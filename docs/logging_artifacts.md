Logging and Artifacts
=====================

Files and Locations
-------------------
- logs/agent.log — text log (per run; appended).
- logs/trace.jsonl — JSON lines; summary at end; includes step/session ids, stop reasons, evidence.
- data/state — JSON artifacts with session/step labels:
  - observation-<session-step>.json
  - planner-<session-step>.json (raw LLM, if ENABLE_RAW_LOGS)
  - execute-<session-step>.json
- data/screenshots — PNG screenshots with session/step labels:
  - observe-<session-step>.png
  - exec-<action>-<session-step>.png (click/type/scroll/etc.)
  - exec-js-click/text-click variants for fallbacks.
- data/user_data — persistent profile.

Labeling
--------
- session_id generated per run; step_id per node execution.
- Filenames include session/step for correlation; trace records include paths (planner_raw_path, exec_result_path).

Trace Fields (common)
---------------------
- step, session_id, step_id
- action (planner/executor)
- planner_retries
- security_requires_confirmation
- execute_success/execute_error
- exec_result_path/planner_raw_path
- loop_trigger, loop_trigger_sig
- attempts_per_element, max_attempts_per_element
- stop_reason/stop_details, terminal_reason/type, goal_stage (summary)

Observation/Execute JSON
------------------------
- observation: url, title, mapping (elements with id/tag/text/role/zone/is_fixed/is_nav/attrs), screenshot_path, recorded_at.
- execute: success, action, error, screenshot_path, recorded_at.

Cleaning
--------
- `--clean-between-goals` removes logs/state/screenshots folders between goals and recreates them (profile stays).

Viewing
-------
- Use trace.jsonl for step-by-step debugging; map step/session to screenshots and state JSONs.

Related module docs
-------------------
- [docs/modules/termination_normalizer.md](/docs/modules/termination_normalizer.md) (terminal mapping/summary)
- [docs/modules/execute.md](/docs/modules/execute.md) (execute artifacts)
- [docs/modules/observe.md](/docs/modules/observe.md) (observation artifacts)
