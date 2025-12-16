Module: src/agent/state.py
==========================

Responsibility
--------------
- Lightweight state holder for legacy/custom loop (not used in LangGraph path, retained for completeness).

Components
----------
- AgentState:
  - fields: max_observations (default 5), observations (list of Observation).
  - add_observation(obs): append and keep only last max_observations.
  - recent_observations(limit=3): return last N observations.

Notes
-----
- Legacy loop (src/agent/loop.py) is frozen; primary execution uses LangGraph. AgentState remains as a simple ring buffer utility.
