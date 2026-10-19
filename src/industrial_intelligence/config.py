"""Environment-based configuration with conservative local defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROFILE_ROWS = {"small": 10_000, "medium": 100_000, "full": 1_000_000}


def _float_env(name: str, default: float) -> float:
    value = float(os.getenv(name, default))
    if not 0 <= value <= 0.1:
        raise ValueError(f"{name} must be between 0 and 0.1")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration shared by generator, pipeline, and services."""

    profile: str = "small"
    seed: int = 20_261_019
    data_dir: Path = Path("data")
    chunk_size: int = 10_000
    invalid_rate: float = 0.005

    @property
    def measurement_count(self) -> int:
        try:
            return PROFILE_ROWS[self.profile]
        except KeyError as exc:
            raise ValueError(f"Unknown profile {self.profile!r}; use small, medium, or full") from exc

    @classmethod
    def from_env(cls, profile: str | None = None) -> "Settings":
        return cls(
            profile=profile or os.getenv("IIP_PROFILE", "small"),
            seed=int(os.getenv("IIP_SEED", "20261019")),
            data_dir=Path(os.getenv("IIP_DATA_DIR", "data")),
            chunk_size=int(os.getenv("IIP_CHUNK_SIZE", "10000")),
            invalid_rate=_float_env("IIP_INJECT_INVALID_RATE", 0.005),
        )

