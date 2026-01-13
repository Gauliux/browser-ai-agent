Browser Integration
===================

Launch & Context
----------------
- Playwright Chromium, headful, launch_persistent_context with user_data_dir (persistent profile).
- Args: --start-maximized; viewport optional (env VIEWPORT_*); sync_viewport_with_window optional.
- Active page tracking: set_active_page; on page close selects an alive page; on new page sets active; TargetClosed heuristic used by observe/execute retries.
- switch_tab: planner action sets a hint; execute node switches tab via runtime.set_active_page_by_hint (url/title/index hint); reobserve happens inside the execute flow, not as an extra step.

DOM Annotation (Set-of-Mark)
----------------------------
- JS injected to collect visible interactive elements: a/button/input/textarea/select/[role=button]/[onclick]; filters by bounding box visibility, opacity/visibility/display.
- Adds data-agent-id, optional overlay badge (hidden if HIDE_OVERLAY); records tag/text/role/zone/bbox/fixed/nav/disabled/attr name/id/aria-label.
- Sorted by y/x, nav-like pushed later; zone computed from viewport; mapping balanced across zones; dedupe in paged_scan.
- Mapping limits enforced; mapping boost on loops/errors; goal-aware candidates extracted separately.

Screenshots
-----------
- Observe: optional (on_demand|always); filenames include session/step.
- Planner may recapture with screenshot if needed (small mapping or errors).
- Execute: screenshots for actions and fallbacks with session/step label.

Actions ↔ Playwright
--------------------
- navigate (page.goto), search (type query, Enter; Ctrl+L fallback), go_back/go_forward (history), switch_tab (handled in execute via hint), click/type/scroll/screenshot.
- scroll: wheel if no element, scroll_into_view otherwise; scroll_step configurable.
- type: fill value, optional Enter (TYPE_SUBMIT_FALLBACK).

Fallbacks & Resilience
----------------------
- Execute fallbacks: reobserve (alternating scroll) → JS click → text-match click; avoid list grows per element failures; max_attempts_per_element enforced.
- Reobserve uses capture_observation with same labeling; TargetClosed retried in observe/execute.
- paged_scan: multiple viewport captures with small scrolls; dedup mapping.

State & Artifacts
-----------------
- observation/planner/execute JSONs in data/state with session/step label.
- screenshots in data/screenshots (observe-* / exec-*/js-click/text-click with label).
- Trace/logs capture paths for debugging (planner_raw_path, exec_result_path).
