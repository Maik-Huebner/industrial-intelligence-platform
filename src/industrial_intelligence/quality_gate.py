"""Fail-fast quality gates for source and persisted pipeline stages."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .quality_contract import EXPECTED_MACHINE_COUNT, MAX_REJECTED_FRACTION


class QualityGateError(RuntimeError):
    """Raised for a critical integrity violation."""


def validate_source_gate(data_dir: Path) -> dict[str, object]:
    """Validate the MongoDB export and tolerant raw-record quarantine result."""
    processed = data_dir / "processed"
    export_manifest = json.loads(
        (processed / "mongodb_export" / "manifest.json").read_text(encoding="utf-8")
    )
    quality = json.loads((processed / "quality_report.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((data_dir / "raw" / "manifest.json").read_text(encoding="utf-8"))
    with (data_dir / "raw" / "postgres" / "machines.csv").open(encoding="utf-8") as handle:
        machines = list(csv.DictReader(handle))

    critical: list[str] = []
    source_count = int(export_manifest["source_count"])
    exported_count = int(export_manifest["exported_count"])
    valid = int(quality["valid"])
    rejected = int(quality["rejected"])
    if export_manifest.get("source") != "mongodb" or quality.get("source") != "mongodb_export":
        critical.append("unverified_source")
    if source_count != exported_count:
        critical.append("incomplete_mongodb_export")
    if exported_count != int(source_manifest["sensor_readings"]):
        critical.append("source_manifest_count_mismatch")
    if valid + rejected != exported_count:
        critical.append("validation_count_mismatch")
    if int(export_manifest["duplicate_reading_ids"]) != 0 or int(quality["duplicates"]) != 0:
        critical.append("duplicate_reading_ids")
    if int(export_manifest["missing_reading_ids"]) != 0:
        critical.append("missing_reading_ids")
    if valid == 0:
        critical.append("empty_valid_dataset")
    if len(machines) != EXPECTED_MACHINE_COUNT:
        critical.append("unexpected_machine_count")
    rejected_fraction = rejected / max(1, valid + rejected)
    if rejected_fraction > MAX_REJECTED_FRACTION:
        critical.append("rejected_fraction_exceeded")
    if critical:
        raise QualityGateError("Source quality gate failed: " + ", ".join(sorted(critical)))
    return {
        "gate": "source",
        "status": "passed",
        "source": "mongodb",
        "input_rows": exported_count,
        "valid_rows": valid,
        "rejected_rows": rejected,
        "rejected_fraction": rejected_fraction,
        "machine_references": len(machines),
        "tolerated_defects": dict(quality.get("reasons", {})),
    }
