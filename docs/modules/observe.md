Module: src/agent/core/observe.py
=================================

Responsibility
--------------
- Захват Observation: аннотированная карта интерактивных элементов (Set-of-Mark), опциональный скрин, зона-балансировка, сохранение артефактов.
- Используется в узлах observe/execute фолбэках/paged_scan.

Key Components
--------------
- JS_SET_OF_MARK: отмечает видимые интерактивные элементы, data-agent-id, overlay номера (если не скрыт), собирает tag/text/role/zone/bbox/is_fixed/is_nav/is_disabled/attrs.
- Data classes: BoundingBox, ElementMark (с is_disabled), Observation; ObservationRecorder сохраняет JSON.
- Helpers: collect_marks, capture_observation, zone balancing, label sanitization.

Behavior
--------
- collect_marks(page, max_elements, viewports): JS-инъекция, фильтр видимости, ids по y/x, overlay если не скрыт, сортировка по y/x.
- capture_observation(...):
  - Опциональный sync viewport с window.innerWidth/Height.
  - Эффективный mapping_limit = settings.mapping_limit (+ _mapping_boost при paged_scan/loop).
  - Zone balancing: round-robin по зонам (top/mid/bottom) с приоритетом fixed/nav.
  - Скрин по observe_screenshot_mode (on_demand|always); имена включают label.
  - Сохраняет Observation JSON/скрин в paths.state_dir/paths.screenshots_dir.
- _prioritize_mapping/_apply_zone_balancing: сортировка и балансировка, сохраняет is_disabled.

Settings Used
-------------
- mapping_limit (+ _mapping_boost), observe_screenshot_mode, hide_overlay, sync_viewport_with_window, viewport sizes, paths.state_dir, paths.screenshots_dir.

Integration Points
------------------
- node_observe (первичный захват, goal-aware retries для sparse listing).
- execute_with_fallbacks (reobserve при фейлах), paged_scan, planner screenshot recapture.
