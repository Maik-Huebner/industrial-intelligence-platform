import csv
import json

import pytest

from industrial_intelligence.quality_gate import QualityGateError, validate_source_gate


def write_gate_inputs(tmp_path, *, source_count=100, exported_count=100, valid=99, rejected=1):
    (tmp_path / "processed/mongodb_export").mkdir(parents=True)
    (tmp_path / "raw/postgres").mkdir(parents=True)
    (tmp_path / "processed/mongodb_export/manifest.json").write_text(
        json.dumps(
            {
                "source": "mongodb",
                "source_count": source_count,
                "exported_count": exported_count,
                "duplicate_reading_ids": 0,
                "missing_reading_ids": 0,
            }
        )
    )
    (tmp_path / "processed/quality_report.json").write_text(
        json.dumps(
            {
                "source": "mongodb_export",
                "valid": valid,
                "rejected": rejected,
                "duplicates": 0,
                "reasons": {"missing_temperature_c": rejected},
            }
        )
    )
    (tmp_path / "raw/manifest.json").write_text(json.dumps({"sensor_readings": source_count}))
    with (tmp_path / "raw/postgres/machines.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["machine_id"])
        writer.writeheader()
        writer.writerows({"machine_id": f"M-{number:03d}"} for number in range(1, 51))


def test_source_gate_accepts_tolerable_quarantine(tmp_path) -> None:
    write_gate_inputs(tmp_path)
    report = validate_source_gate(tmp_path)
    assert report["status"] == "passed"
    assert report["rejected_fraction"] == 0.01


def test_source_gate_stops_incomplete_export(tmp_path) -> None:
    write_gate_inputs(tmp_path, exported_count=99)
    with pytest.raises(QualityGateError, match="incomplete_mongodb_export"):
        validate_source_gate(tmp_path)
