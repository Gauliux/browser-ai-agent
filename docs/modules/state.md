Module: src/agent/legacy/state.py
=================================

Responsibility
--------------
- Simple observation store for the legacy loop (LangGraph does not use it).

Components
----------
- AgentState:
  - fields: max_observations (default 5), observations (list of Observation).
  - add_observation(obs): append and trim to max_observations.
  - recent_observations(limit=3): last N observations.

Notes
-----
- Legacy loop (src/agent/legacy/loop.py) is frozen; AgentState remains as a ring buffer utility.
