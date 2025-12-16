Module: src/agent/tracing.py
============================

Responsibility
--------------
- Provide simple logging utilities for text and JSONL traces; generate step ids; save observation snapshots.

Components
----------
- generate_step_id(prefix): returns prefix-<8 hex chars>.
- TraceLogger: writes dict/dataclass/other to JSONL (asdict or to_dict if available; dict written as-is).
- TextLogger: appends plain text lines.
- save_observation_snapshot: writes observation JSON to a path with indent.

Usage
-----
- TextLogger/TraceLogger created in main.py and passed into LangGraph runner (if available).
- LangGraph nodes write records and final summary via trace.write/log.write.
