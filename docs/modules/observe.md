Module: src/agent/core/observe.py
=================================

Responsibility
--------------
- Capture Observation: annotated map of interactive elements (Set-of-Mark), optional screenshot, zone balancing, artifact saving.
- Used in observe/execute fallbacks/paged_scan nodes.

Key Components
--------------
- JS_SET_OF_MARK: marks visible interactive elements, data-agent-id, overlay numbers (if not hidden), collects tag/text/role/zone/bbox/is_fixed/is_nav/is_disabled/attrs.
- Data classes: BoundingBox, ElementMark (with is_disabled), Observation; ObservationRecorder saves JSON.
- Helpers: collect_marks, capture_observation, zone balancing, label sanitization.

Behavior
--------
- collect_marks(page, max_elements, viewports): JS injection, visibility filter, ids by y/x, overlay if not hidden, sorting by y/x.
- capture_observation(...):
  - Optional viewport sync with window.innerWidth/Height.
  - Effective mapping_limit = settings.mapping_limit (+ _mapping_boost during paged_scan/loop).
  - Zone balancing: round-robin across zones (top/mid/bottom) prioritizing fixed/nav.
  - Screenshot per observe_screenshot_mode (on_demand|always); names include label.
  - Saves Observation JSON/screenshot to paths.state_dir/paths.screenshots_dir.
- _prioritize_mapping/_apply_zone_balancing: sorting and balancing; preserves is_disabled.

Settings Used
-------------
- mapping_limit (+ _mapping_boost), observe_screenshot_mode, hide_overlay, sync_viewport_with_window, viewport sizes, paths.state_dir, paths.screenshots_dir.

Integration Points
------------------
- node_observe (primary capture, goal-aware retries for sparse listing).
- execute_with_fallbacks (reobserve on failures), paged_scan, planner screenshot recapture.
