"""Shared semantic contract for raw industrial sensor readings."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

REQUIRED_FIELDS = (
    "reading_id",
    "machine_id",
    "timestamp",
    "temperature_c",
    "vibration_mm_s",
    "power_kw",
    "load_pct",
)

SENSOR_RANGES: dict[str, tuple[float, float]] = {
    "temperature_c": (-40.0, 180.0),
    "vibration_mm_s": (0.0, 50.0),
    "power_kw": (0.0, 500.0),
    "load_pct": (0.0, 100.0),
}

EXPECTED_MACHINE_COUNT = 50
MAX_REJECTED_FRACTION = 0.02


def semantic_errors(record: Mapping[str, object], machine_ids: set[str]) -> list[str]:
    """Return stable reason codes used by both Python and Spark validation."""
    errors: list[str] = []
    for key in REQUIRED_FIELDS:
        if record.get(key) in (None, ""):
            errors.append(f"missing_{key}")
    if record.get("machine_id") not in machine_ids:
        errors.append("unknown_machine_id")
    try:
        datetime.fromisoformat(str(record.get("timestamp")))
    except (TypeError, ValueError):
        errors.append("invalid_timestamp")
    for key, (lower, upper) in SENSOR_RANGES.items():
        value = record.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            errors.append(f"non_numeric_{key}")
            continue
        if not lower <= numeric <= upper:
            errors.append(f"out_of_range_{key}")
    return sorted(set(errors))
