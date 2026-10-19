"""Domain records used by the deterministic synthetic-data generator."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Machine:
    machine_id: str
    line_id: str
    machine_type: str
    installed_year: int
    criticality: int
    manufacturer: str

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SensorReading:
    reading_id: str
    machine_id: str
    timestamp: str
    temperature_c: float | None
    vibration_mm_s: float | None
    power_kw: float | None
    load_pct: float | None
    operating_state: str
    scenario: str
    source: str = "synthetic-generator-v1"

    def as_document(self) -> dict[str, object]:
        return {
            "reading_id": self.reading_id,
            "machine_id": self.machine_id,
            "timestamp": self.timestamp,
            "sensors": {
                "temperature": {"value": self.temperature_c, "unit": "°C"},
                "vibration": {"value": self.vibration_mm_s, "unit": "mm/s"},
                "power": {"value": self.power_kw, "unit": "kW"},
                "load": {"value": self.load_pct, "unit": "%"},
            },
            "context": {"operating_state": self.operating_state, "scenario": self.scenario},
            "lineage": {"source": self.source, "schema_version": 1},
        }

