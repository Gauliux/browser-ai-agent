from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agent.observe import Observation


def generate_step_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TraceLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: Any) -> None:
        if isinstance(record, dict):
            payload = record
        elif hasattr(record, "to_dict"):
            payload = record.to_dict()  # type: ignore[call-arg]
        else:
            try:
                payload = asdict(record)
            except Exception:
                payload = {"value": str(record)}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


class TextLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")


def save_observation_snapshot(observation: Observation, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(observation.to_dict(), f, ensure_ascii=False, indent=2)
