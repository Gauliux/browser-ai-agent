Module: src/agent/execute.py
============================

Responsibility
--------------
- Execute planner actions via Playwright; capture results and screenshots; persist execution artifacts.
- Provide fallback chain and avoid/retry logic.

Data Structures
---------------
- ExecutionResult: success, action, error, screenshot_path, recorded_at; to_dict().
- save_execution_result: save ExecutionResult JSON with optional label to state_dir.

Action Execution
----------------
- Supported actions: done/ask_user (meta), go_back/go_forward, navigate (value required), search (type query + Enter, with Ctrl+L fallback), scroll (mouse wheel or scroll_into_view), click, type (fill + optional Enter), screenshot.
- Screenshots: _capture/_maybe_capture, filenames include label (often session-step).
- _locate_element: find by data-agent-id; raises if missing.

Fallback Chain (execute_with_fallbacks)
---------------------------------------
- Initial execute_action; if fail (non-meta), retries up to max_reobserve_attempts:
  - Optional wiggle scroll (alternating direction, scroll_step setting).
  - Reobserve via capture_observation (labelled), then retry execute_action.
- If still failing and action is click:
  - JS click on element id; then text-match click by element text.
- Per-element failures tracked by caller (LangGraph execute_node) to avoid elements.
- Artifacts (screenshots and observations) use unified label (session-step if provided).

Settings Used
-------------
- paths.screenshots_dir, paths.state_dir; type_submit_fallback; scroll_step; hide_overlay; max_reobserve_attempts (passed by caller); max_attempts_per_element enforced in caller.

Integration Points
------------------
- langgraph_loop execute_node wraps execute_with_fallbacks, saves ExecutionResult via save_execution_result, tracks avoid/fail counts and state changes.
