Module: src/agent/infra/tracing.py
==================================

Responsibility
--------------
- Lightweight logging helpers used across the agent.
- Provide stable step/session IDs.

API
---
- generate_step_id(prefix: str) -> str: random short ID with prefix.
- TraceLogger(path): write JSONL records (dict/dataclass/objects with to_dict).
- TextLogger(path): append plain text lines.
- save_observation_snapshot(observation, path): write Observation snapshot JSON.

Used By
-------
- main.py, io/ui_shell.py, langgraph_loop facade, node_* implementations (records + summaries).
