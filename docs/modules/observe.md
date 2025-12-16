Module: src/agent/observe.py
============================

Responsibility
--------------
- Capture page observations: annotated mapping of interactive elements, optional screenshot, zone balancing, and persistence to state files.
- Provide JS Set-of-Mark injector to tag elements with data-agent-id and collect metadata.

Key Components
--------------
- JS_SET_OF_MARK: annotates visible interactive elements, applies overlay badges (unless hidden), records tag/text/role/zone/bbox/is_fixed/is_nav/disabled/attrs.
- Data classes: BoundingBox, ElementMark, Observation; ObservationRecorder saves JSON to state_dir.
- Helpers: collect_marks, capture_observation, zone balancing, label sanitization.

Behavior
--------
- collect_marks(page, max_elements, viewports): injects JS, filters by visibility, assigns incremental ids, optional overlay, returns ElementMark list sorted by y/x.
- capture_observation(...):
  - Optional viewport sync with window.innerWidth/Height (thresholded).
  - Effective mapping limit = settings.mapping_limit (+ optional boost on page attribute).
  - Zone balancing: distributes elements across zones (top/mid/bottom) with priority fixed > normal > nav.
  - Optional screenshot (observe_screenshot_mode on_demand|always); filenames include sanitized label.
  - Saves Observation JSON via ObservationRecorder (label optional); returns Observation with url/title/mapping/screenshot_path/timestamp.
- _prioritize_mapping: nav to end, fixed first, then y/x.
- _apply_zone_balancing: round-robin across zones up to limit.

Settings Used
-------------
- mapping_limit (+ page._mapping_boost), observe_screenshot_mode, hide_overlay, sync_viewport_with_window, viewport sizes, paths.state_dir, paths.screenshots_dir.

Integration Points
------------------
- langgraph_loop observe_node, execute fallbacks (reobserve), paged_scan, planner screenshot recapture.
- execute_with_fallbacks uses capture_observation for retries.
