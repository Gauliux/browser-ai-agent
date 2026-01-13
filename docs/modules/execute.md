Module: src/agent/core/execute.py
=================================

Responsibility
--------------
- Execute planner actions via Playwright; capture results/screenshots; persist execution artifacts.
- Provide fallback chain and best-effort resilience for flaky DOM.

Data Structures
---------------
- ExecutionResult: success, action, error, screenshot_path, recorded_at; to_dict().
- save_execution_result: save ExecutionResult JSON (labeled) to paths.state_dir.

Action Execution
----------------
- Supported actions: done/ask_user (meta), go_back/go_forward, navigate (value required),
  search (if element_id provided: focus/scroll element, fill query, press Enter; else type + Enter with Ctrl+L fallback), scroll, click, type (fill + optional Enter), screenshot.
- switch_tab is first-class: tab switch is handled by runtime/execute-node; execution should not treat tab-switch as a failure.
- Screenshots: filenames include label (typically session-step).

Fallback Chain (execute_with_fallbacks)
---------------------------------------
- Initial execute_action; if it fails (non-meta), retries up to max_reobserve_attempts:
  - Optional wiggle scroll (alternating direction, scroll_step).
  - Reobserve via capture_observation (labeled), then retry execute_action.
- If still failing and action=click: JS click by element id → text-match click by text.
- Per-element failures/avoid-list is managed by the execute node (graph), not this module.

Settings Used
-------------
- paths.screenshots_dir, paths.state_dir; type_submit_fallback; scroll_step; max_reobserve_attempts (passed in).

Integration Points
------------------
- node_execute handles tabs/context_events/records/UX and wraps execute_with_fallbacks + save_execution_result.
