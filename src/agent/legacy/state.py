from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from agent.core.observe import Observation


@dataclass
class AgentState:
    max_observations: int = 5
    observations: List[Observation] = field(default_factory=list)

    def add_observation(self, obs: Observation) -> None:
        self.observations.append(obs)
        if len(self.observations) > self.max_observations:
            self.observations = self.observations[-self.max_observations :]

    def recent_observations(self, limit: int = 3) -> List[Observation]:
        return self.observations[-limit:]
