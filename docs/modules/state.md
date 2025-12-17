Module: src/agent/legacy/state.py
=================================

Responsibility
--------------
- Простое хранилище наблюдений для legacy цикла (LangGraph его не использует).

Components
----------
- AgentState:
  - fields: max_observations (default 5), observations (list of Observation).
  - add_observation(obs): append и обрезает до max_observations.
  - recent_observations(limit=3): последние N наблюдений.

Notes
-----
- Legacy loop (src/agent/legacy/loop.py) заморожен; AgentState остаётся как ring buffer утилита.
