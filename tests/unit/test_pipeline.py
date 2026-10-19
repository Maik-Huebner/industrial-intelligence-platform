import csv
from pathlib import Path

from industrial_intelligence.config import Settings
from industrial_intelligence.pipeline import run_local_pipeline


def test_local_pipeline_scores_all_machines(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(profile="small", seed=123, data_dir=tmp_path / "data", invalid_rate=0.005)
    summary = run_local_pipeline(settings)
    assert summary["status"] == "success"
    assert summary["machines_scored"] == 50
    assert summary["quality"]["valid"] + summary["quality"]["rejected"] == 10_000
    with (tmp_path / "data/processed/machine_metrics.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 50
    assert rows[0]["score_method"] == "transparent-rule-baseline-v1"

