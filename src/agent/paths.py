from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Paths:
    root: Path
    user_data_dir: Path
    screenshots_dir: Path
    state_dir: Path
    logs_dir: Path

    @classmethod
    def from_env(cls, root: Path) -> "Paths":
        root = root.resolve()

        def _resolve(var_name: str, default: Path) -> Path:
            value = os.getenv(var_name)
            return Path(value).expanduser().resolve() if value else default.resolve()

        base_data = root / "data"
        return cls(
            root=root,
            user_data_dir=_resolve("USER_DATA_DIR", base_data / "user_data"),
            screenshots_dir=_resolve("SCREENSHOTS_DIR", base_data / "screenshots"),
            state_dir=_resolve("STATE_DIR", base_data / "state"),
            logs_dir=_resolve("LOGS_DIR", root / "logs"),
        )

    def ensure(self) -> None:
        for folder in self._all_folders():
            folder.mkdir(parents=True, exist_ok=True)

    def _all_folders(self) -> Iterable[Path]:
        return (
            self.user_data_dir,
            self.screenshots_dir,
            self.state_dir,
            self.logs_dir,
        )
