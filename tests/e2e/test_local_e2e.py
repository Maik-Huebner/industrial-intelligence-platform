import json
from pathlib import Path

import pytest

from industrial_intelligence.config import Settings
from industrial_intelligence.pipeline import run_local_pipeline


@pytest.mark.e2e
def test_generate_validate_transform_score_and_serve_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    summary = run_local_pipeline(Settings(profile="small", seed=20261019, data_dir=Path("data")))
    report = json.loads(Path("reports/latest_pipeline_run.json").read_text())
    predictions = json.loads(Path("data/processed/predictions.json").read_text())
    assert report["run_id"] == summary["run_id"]
    assert len(predictions) == 50
    assert {row["risk_label"] for row in predictions} <= {"low", "medium", "high"}

