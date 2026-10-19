"""Chunked, deterministic generator for a coherent industrial data estate."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .config import Settings
from .models import Machine, SensorReading

LOGGER = logging.getLogger(__name__)
MACHINE_TYPES = ("CNC", "PRESS", "PUMP", "ROBOT", "CONVEYOR")
MANUFACTURERS = ("KernTech", "RheinMotion", "NordWerk")


def stable_id(prefix: str, *parts: object) -> str:
    """Return a stable, compact identifier without process-dependent hashing."""
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


class IndustrialDataGenerator:
    """Generate master, event, and time-series data from a fixed seed."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.random = random.Random(settings.seed)
        self.raw_dir = settings.data_dir / "raw"

    def machines(self) -> list[Machine]:
        machines: list[Machine] = []
        for number in range(1, 51):
            machines.append(
                Machine(
                    machine_id=f"M-{number:03d}",
                    line_id=f"LINE-{((number - 1) // 10) + 1:02d}",
                    machine_type=MACHINE_TYPES[(number - 1) % len(MACHINE_TYPES)],
                    installed_year=2011 + ((number * 7) % 15),
                    criticality=1 + ((number * 3) % 5),
                    manufacturer=MANUFACTURERS[(number - 1) % len(MANUFACTURERS)],
                )
            )
        return machines

    def readings(self) -> Iterator[SensorReading]:
        """Yield readings without retaining the full profile in memory."""
        count = self.settings.measurement_count
        start = datetime(2026, 7, 11, tzinfo=UTC)
        machine_count = 50
        steps_per_machine = math.ceil(count / machine_count)
        for index in range(count):
            machine_number = (index % machine_count) + 1
            step = index // machine_count
            machine_id = f"M-{machine_number:03d}"
            timestamp = start + timedelta(seconds=(100 * 24 * 3600 / steps_per_machine) * step)
            phase = 2 * math.pi * (step % 144) / 144
            age = (machine_number * 7 % 15) / 15
            load = max(0.0, min(100.0, 63 + 24 * math.sin(phase) + self.random.gauss(0, 5)))
            stressed = machine_number in {7, 17, 28, 39, 46} and step > steps_per_machine * 0.62
            wear = (step / steps_per_machine) * (1.2 + age) + (1.5 if stressed else 0)
            temp = 39 + 0.19 * load + 3.1 * wear + self.random.gauss(0, 1.6)
            vibration = 1.3 + 0.021 * load + 0.72 * wear + self.random.gauss(0, 0.25)
            power = 7 + 0.31 * load + 1.2 * wear + self.random.gauss(0, 1.1)
            scenario = "progressive_wear" if stressed else "normal_operation"
            operating_state = "idle" if load < 18 else "running"
            if self.random.random() < 0.012 + (0.055 if stressed else 0):
                scenario = "thermal_vibration_anomaly"
                temp += self.random.uniform(8, 18)
                vibration += self.random.uniform(2.5, 5.5)
            temperature_value: float | None = round(temp, 3)
            machine_value = machine_id
            if self.settings.invalid_rate and self.random.random() < self.settings.invalid_rate:
                defect = self.random.choice(("missing_temperature", "range", "machine"))
                if defect == "missing_temperature":
                    temperature_value = None
                elif defect == "range":
                    temperature_value = 999.0
                else:
                    machine_value = "UNKNOWN"
            yield SensorReading(
                reading_id=stable_id("R", self.settings.seed, index),
                machine_id=machine_value,
                timestamp=timestamp.isoformat(),
                temperature_c=temperature_value,
                vibration_mm_s=round(vibration, 3),
                power_kw=round(power, 3),
                load_pct=round(load, 3),
                operating_state=operating_state,
                scenario=scenario,
            )

    def generate(self) -> dict[str, int]:
        """Write source-oriented files and return the generated record counts."""
        for source in ("postgres", "mongodb", "files", "neo4j"):
            (self.raw_dir / source).mkdir(parents=True, exist_ok=True)
        machines = self.machines()
        self._write_machines(machines)
        event_counts = self._write_events(machines)
        self._write_components(machines)
        sensor_path = self.raw_dir / "mongodb" / "sensor_readings.jsonl"
        sensor_count = 0
        with sensor_path.open("w", encoding="utf-8") as handle:
            for reading in self.readings():
                handle.write(json.dumps(reading.as_document(), ensure_ascii=False) + "\n")
                sensor_count += 1
                if sensor_count % self.settings.chunk_size == 0:
                    handle.flush()
                    LOGGER.info("sensor_generation_chunk", extra={"records": sensor_count})
        manifest = {
            "profile": self.settings.profile,
            "seed": self.settings.seed,
            "sensor_readings": sensor_count,
            "machines": len(machines),
            **event_counts,
        }
        (self.raw_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        return manifest

    def _write_machines(self, machines: list[Machine]) -> None:
        path = self.raw_dir / "postgres" / "machines.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(machines[0].as_dict()))
            writer.writeheader()
            writer.writerows(machine.as_dict() for machine in machines)
        orders_path = self.raw_dir / "postgres" / "production_orders.csv"
        rng = random.Random(self.settings.seed + 11)
        with orders_path.open("w", newline="", encoding="utf-8") as handle:
            fields = ["order_id", "line_id", "product_code", "planned_units", "started_at", "status"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index in range(600):
                writer.writerow(
                    {
                        "order_id": f"PO-{index + 1:05d}",
                        "line_id": f"LINE-{(index % 5) + 1:02d}",
                        "product_code": f"PART-{rng.randint(1, 35):03d}",
                        "planned_units": rng.randint(80, 2500),
                        "started_at": (datetime(2026, 7, 11, tzinfo=UTC) + timedelta(hours=index * 4)).isoformat(),
                        "status": rng.choice(("completed", "completed", "in_progress", "cancelled")),
                    }
                )

    def _write_events(self, machines: list[Machine]) -> dict[str, int]:
        rng = random.Random(self.settings.seed + 23)
        start = datetime(2026, 7, 11, tzinfo=UTC)
        maintenance_count = 320
        failure_count = 180
        maintenance_path = self.raw_dir / "files" / "maintenance.csv"
        with maintenance_path.open("w", newline="", encoding="utf-8") as handle:
            fields = ["maintenance_id", "machine_id", "performed_at", "maintenance_type", "duration_minutes", "notes"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index in range(maintenance_count):
                machine = machines[(index * 13) % len(machines)]
                writer.writerow(
                    {
                        "maintenance_id": f"MAINT-{index + 1:05d}",
                        "machine_id": machine.machine_id,
                        "performed_at": (start + timedelta(hours=rng.randint(0, 2399))).isoformat(),
                        "maintenance_type": rng.choice(("inspection", "lubrication", "replacement", "calibration")),
                        "duration_minutes": rng.randint(20, 480),
                        "notes": rng.choice(("routine", "bearing noise", "temperature alarm", "scheduled service")),
                    }
                )
        failures = []
        for index in range(failure_count):
            machine_number = [7, 17, 28, 39, 46][index % 5] if index < 70 else ((index * 17) % 50) + 1
            failures.append(
                {
                    "failure_id": f"FAIL-{index + 1:05d}",
                    "machine_id": f"M-{machine_number:03d}",
                    "occurred_at": (start + timedelta(hours=rng.randint(0, 2399))).isoformat(),
                    "failure_type": rng.choice(("bearing", "overheat", "hydraulic", "control")),
                    "severity": rng.choice(("low", "medium", "high", "critical")),
                    "downtime_minutes": rng.randint(5, 720),
                }
            )
        (self.raw_dir / "files" / "failures.json").write_text(
            json.dumps(failures, indent=2), encoding="utf-8"
        )
        return {"maintenance_records": maintenance_count, "failure_events": failure_count, "production_orders": 600}

    def _write_components(self, machines: list[Machine]) -> None:
        path = self.raw_dir / "neo4j" / "machine_components.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            fields = ["component_id", "machine_id", "component_type", "shared_dependency_id"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for machine in machines:
                for component_type in ("motor", "bearing", "cooling", "controller"):
                    writer.writerow(
                        {
                            "component_id": f"{machine.machine_id}-{component_type.upper()}",
                            "machine_id": machine.machine_id,
                            "component_type": component_type,
                            "shared_dependency_id": f"UTILITY-{machine.line_id}-{component_type}",
                        }
                    )
