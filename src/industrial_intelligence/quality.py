"""Validation and quarantine for raw sensor documents."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class QualityReport:
    valid: int = 0
    rejected: int = 0
    duplicates: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def reject(self, reasons: Iterable[str]) -> None:
        self.rejected += 1
        for reason in reasons:
            self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "rejected": self.rejected,
            "duplicates": self.duplicates,
            "reasons": dict(sorted(self.reasons.items())),
        }


def flatten_document(document: dict[str, object]) -> dict[str, object]:
    sensors = document.get("sensors") or {}
    context = document.get("context") or {}
    lineage = document.get("lineage") or {}
    return {
        "reading_id": document.get("reading_id"),
        "machine_id": document.get("machine_id"),
        "timestamp": document.get("timestamp"),
        "temperature_c": (sensors.get("temperature") or {}).get("value"),
        "vibration_mm_s": (sensors.get("vibration") or {}).get("value"),
        "power_kw": (sensors.get("power") or {}).get("value"),
        "load_pct": (sensors.get("load") or {}).get("value"),
        "operating_state": context.get("operating_state"),
        "scenario": context.get("scenario"),
        "source": lineage.get("source"),
    }


def validation_errors(record: dict[str, object], machine_ids: set[str]) -> list[str]:
    """Return stable reason codes for a flattened sensor record."""
    errors: list[str] = []
    required = ("reading_id", "machine_id", "timestamp", "vibration_mm_s", "power_kw", "load_pct")
    for key in required:
        if record.get(key) in (None, ""):
            errors.append(f"missing_{key}")
    if record.get("temperature_c") is None:
        errors.append("missing_temperature_c")
    if record.get("machine_id") not in machine_ids:
        errors.append("unknown_machine_id")
    try:
        datetime.fromisoformat(str(record.get("timestamp")))
    except ValueError:
        errors.append("invalid_timestamp")
    ranges = {
        "temperature_c": (-40, 180),
        "vibration_mm_s": (0, 50),
        "power_kw": (0, 500),
        "load_pct": (0, 100),
    }
    for key, (lower, upper) in ranges.items():
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


def validate_sensor_file(data_dir: Path) -> QualityReport:
    """Normalize valid JSONL records and quarantine invalid or duplicate rows."""
    raw = data_dir / "raw" / "mongodb" / "sensor_readings.jsonl"
    machines_path = data_dir / "raw" / "postgres" / "machines.csv"
    processed_dir = data_dir / "processed"
    quarantine_dir = data_dir / "quarantine"
    processed_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    with machines_path.open(encoding="utf-8") as handle:
        machine_ids = {row["machine_id"] for row in csv.DictReader(handle)}
    fields = [
        "reading_id",
        "machine_id",
        "timestamp",
        "temperature_c",
        "vibration_mm_s",
        "power_kw",
        "load_pct",
        "operating_state",
        "scenario",
        "source",
    ]
    report = QualityReport()
    seen: set[str] = set()
    with (
        raw.open(encoding="utf-8") as source,
        (processed_dir / "sensor_readings.csv").open("w", newline="", encoding="utf-8") as valid_handle,
        (quarantine_dir / "sensor_readings.jsonl").open("w", encoding="utf-8") as rejected_handle,
    ):
        writer = csv.DictWriter(valid_handle, fieldnames=fields)
        writer.writeheader()
        for line_number, line in enumerate(source, start=1):
            try:
                document = json.loads(line)
                record = flatten_document(document)
                reading_id = str(record.get("reading_id"))
                reasons = validation_errors(record, machine_ids)
            except json.JSONDecodeError:
                document = {"raw": line.rstrip("\n")}
                record = {}
                reading_id = ""
                reasons = ["invalid_json"]
            if reading_id and reading_id in seen:
                reasons.append("duplicate_reading_id")
                report.duplicates += 1
            if reasons:
                report.reject(reasons)
                rejected_handle.write(
                    json.dumps({"line": line_number, "reasons": reasons, "record": document}, ensure_ascii=False) + "\n"
                )
                continue
            seen.add(reading_id)
            writer.writerow(record)
            report.valid += 1
    (processed_dir / "quality_report.json").write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return report

