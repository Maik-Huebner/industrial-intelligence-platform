"""Validation and quarantine for raw sensor documents."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .quality_contract import semantic_errors


@dataclass(slots=True)
class QualityReport:
    valid: int = 0
    rejected: int = 0
    duplicates: int = 0
    reasons: dict[str, int] = field(default_factory=dict)
    source: str = "raw_generator_file"

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
            "source": self.source,
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
    return semantic_errors(record, machine_ids)


def validate_sensor_file(
    data_dir: Path,
    source_path: Path | None = None,
    source_name: str = "raw_generator_file",
) -> QualityReport:
    """Normalize valid JSONL records and quarantine invalid or duplicate rows."""
    raw = source_path or data_dir / "raw" / "mongodb" / "sensor_readings.jsonl"
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
    report = QualityReport(source=source_name)
    seen: set[str] = set()
    previous_reading_id = ""
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
            is_duplicate = (
                reading_id == previous_reading_id
                if source_name == "mongodb_export"
                else reading_id in seen
            )
            if reading_id and is_duplicate:
                reasons.append("duplicate_reading_id")
                report.duplicates += 1
            if reasons:
                report.reject(reasons)
                rejected_handle.write(
                    json.dumps({"line": line_number, "reasons": reasons, "record": document}, ensure_ascii=False) + "\n"
                )
                continue
            if source_name == "mongodb_export":
                previous_reading_id = reading_id
            else:
                seen.add(reading_id)
            writer.writerow(record)
            report.valid += 1
    (processed_dir / "quality_report.json").write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return report
