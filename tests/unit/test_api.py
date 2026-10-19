from pathlib import Path

from fastapi.testclient import TestClient

from industrial_intelligence.api.main import app
from industrial_intelligence.config import Settings
from industrial_intelligence.pipeline import run_local_pipeline


def test_api_serves_pipeline_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IIP_DATA_DIR", str(tmp_path / "data"))
    run_local_pipeline(Settings(profile="small", seed=55, data_dir=tmp_path / "data", invalid_rate=0))
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["pipeline_artifacts_available"] is True
    machine = client.get("/machines/M-017")
    assert machine.status_code == 200
    assert machine.json()["machine"]["machine_id"] == "M-017"
    predictions = client.get("/predictions")
    assert predictions.status_code == 200
    assert len(predictions.json()) == 50


def test_unknown_machine_returns_404(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IIP_DATA_DIR", str(tmp_path / "data"))
    run_local_pipeline(Settings(profile="small", seed=56, data_dir=tmp_path / "data", invalid_rate=0))
    assert TestClient(app).get("/machines/M-999").status_code == 404

