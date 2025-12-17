Module: src/agent/core/execute.py
=================================

Responsibility
--------------
- Execute planner actions via Playwright; capture results/screenshots; persist execution artifacts.
- Provide fallback chain and best-effort resilience for flaky DOM.

Data Structures
---------------
- ExecutionResult: success, action, error, screenshot_path, recorded_at; to_dict().
- save_execution_result: save ExecutionResult JSON (labelled) to paths.state_dir.

Action Execution
----------------
- Supported actions: done/ask_user (meta), go_back/go_forward, navigate (value required),
  search (type query + Enter, with Ctrl+L fallback), scroll, click, type (fill + optional Enter), screenshot.
- switch_tab как first-class: переключение активной страницы делается на уровне runtime/execute-node;
  само исполнение не должно трактовать tab-switch как failure.
- Скрины: filenames включают label (обычно session-step).

Fallback Chain (execute_with_fallbacks)
---------------------------------------
- Initial execute_action; если fail (не meta), ретраи до max_reobserve_attempts:
  - Optional wiggle scroll (alternating direction, scroll_step).
  - Reobserve через capture_observation (labelled), затем повтор execute_action.
- Если всё ещё fail и action=click: JS click по element id → text-match click по тексту.
- Per-element failures/avoid-list ведёт execute node (graph), не этот модуль.

Settings Used
-------------
- paths.screenshots_dir, paths.state_dir; type_submit_fallback; scroll_step; max_reobserve_attempts (передаётся извне).

Integration Points
------------------
- node_execute отвечает за табы/context_events/records/UX и оборачивает execute_with_fallbacks + save_execution_result.
