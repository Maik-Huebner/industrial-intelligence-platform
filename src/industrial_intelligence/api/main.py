"""Small read API over the latest processed artifacts."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="Industrial Intelligence API",
    version="0.1.0",
    description="Decision support for synthetic industrial maintenance data.",
)


def _data_dir() -> Path:
    return Path(os.getenv("IIP_DATA_DIR", "data"))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise HTTPException(status_code=503, detail="Pipeline artifacts are not available")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@app.get("/health")
def health() -> dict[str, object]:
    metrics = _data_dir() / "processed" / "machine_metrics.csv"
    return {"status": "ok", "pipeline_artifacts_available": metrics.exists()}


@app.get("/machines")
def machines(limit: int = Query(50, ge=1, le=50)) -> list[dict[str, str]]:
    return _csv_rows(_data_dir() / "raw" / "postgres" / "machines.csv")[:limit]


@app.get("/machines/{machine_id}")
def machine(machine_id: str) -> dict[str, object]:
    master = next((row for row in machines(limit=50) if row["machine_id"] == machine_id), None)
    if master is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    metric = next(
        (row for row in _csv_rows(_data_dir() / "processed" / "machine_metrics.csv") if row["machine_id"] == machine_id),
        None,
    )
    return {"machine": master, "metrics": metric}


@app.get("/predictions")
def predictions(risk: str | None = None) -> list[dict[str, object]]:
    spark_dir = _data_dir() / "processed" / "ml_predictions_json"
    if spark_dir.exists():
        rows = []
        for part in sorted(spark_dir.glob("part-*.json")):
            rows.extend(json.loads(line) for line in part.read_text(encoding="utf-8").splitlines())
        if risk is None:
            return rows
        label = 1 if risk == "high" else 0
        return [row for row in rows if row["predicted_label"] == label]
    path = _data_dir() / "processed" / "predictions.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Predictions are not available")
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in rows if risk is None or row["risk_label"] == risk]


@app.get("/pipeline-runs/latest")
def latest_pipeline_run() -> dict[str, object]:
    path = Path("reports/latest_pipeline_run.json")
    if not path.exists():
        raise HTTPException(status_code=503, detail="No pipeline run has been recorded")
    return json.loads(path.read_text(encoding="utf-8"))
