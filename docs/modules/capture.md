Module: src/agent/infra/capture.py
==================================

Responsibility
--------------
- Обёртки над observe для графа: повторный захват с ретраями и paged_scan.

API
---
- capture_with_retry(runtime, settings, *, capture_screenshot: bool, label: str): ensure_page → capture_observation; retry на TargetClosed/временные ошибки.
- paged_scan(runtime, settings, *, label_prefix=None): несколько observe проходов с автоскроллом (до paged_scan_steps/viewports), повышает mapping_limit через _mapping_boost.

Used By
-------
- node_observe (capture_with_retry), node_loop_mitigation (paged_scan), execute fallbacks.
