Module: src/agent/infra/capture.py
==================================

Responsibility
--------------
- Wrappers around observe for the graph: retrying capture and paged_scan.

API
---
- capture_with_retry(runtime, settings, *, capture_screenshot: bool, label: str): ensure_page → capture_observation; retries on TargetClosed/transient errors.
- paged_scan(runtime, settings, *, label_prefix=None): multiple observe passes with autoscroll (up to paged_scan_steps/viewports), increases mapping_limit via _mapping_boost.

Used By
-------
- node_observe (capture_with_retry), node_loop_mitigation (paged_scan), execute fallbacks.
