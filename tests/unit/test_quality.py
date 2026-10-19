import json
from pathlib import Path

from industrial_intelligence.config import Settings
from industrial_intelligence.generator import IndustrialDataGenerator
from industrial_intelligence.quality import flatten_document, validate_sensor_file, validation_errors


def test_flatten_nested_mongo_document() -> None:
    document = {
        "reading_id": "R-1",
        "machine_id": "M-001",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sensors": {"temperature": {"value": 50}, "vibration": {"value": 2}, "power": {"value": 20}, "load": {"value": 60}},
        "context": {"operating_state": "running", "scenario": "normal_operation"},
        "lineage": {"source": "test"},
    }
    flattened = flatten_document(document)
    assert flattened["temperature_c"] == 50
    assert validation_errors(flattened, {"M-001"}) == []


def test_validation_quarantines_injected_errors(tmp_path: Path) -> None:
    settings = Settings(profile="small", seed=12, data_dir=tmp_path, invalid_rate=0.01)
    IndustrialDataGenerator(settings).generate()
    report = validate_sensor_file(tmp_path)
    assert report.valid > 9_800
    assert report.rejected > 0
    quarantine = tmp_path / "quarantine/sensor_readings.jsonl"
    first = json.loads(quarantine.read_text(encoding="utf-8").splitlines()[0])
    assert first["reasons"]

