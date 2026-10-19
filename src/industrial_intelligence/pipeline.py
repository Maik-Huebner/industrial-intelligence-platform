"""Portable local pipeline for generation, validation, aggregation, and scoring."""

from __future__ import annotations

import csv
import json
import math
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .generator import IndustrialDataGenerator
from .quality import validate_sensor_file


def _event_counts(path: Path, key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if path.suffix == ".csv":
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                counts[row[key]] += 1
    else:
        for row in json.loads(path.read_text(encoding="utf-8")):
            counts[row[key]] += 1
    return counts


def calculate_metrics(data_dir: Path) -> list[dict[str, object]]:
    """Calculate explainable per-machine metrics in one streaming pass."""
    sensor_path = data_dir / "processed" / "sensor_readings.csv"
    accumulators: dict[str, dict[str, object]] = defaultdict(
        lambda: {"count": 0, "temp_sum": 0.0, "temp_sum_sq": 0.0, "temp_max": -math.inf, "vib_sum": 0.0, "load_sum": 0.0, "anomalies": 0}
    )
    with sensor_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            machine = row["machine_id"]
            values = accumulators[machine]
            temperature = float(row["temperature_c"])
            vibration = float(row["vibration_mm_s"])
            load = float(row["load_pct"])
            values["count"] = int(values["count"]) + 1
            values["temp_sum"] = float(values["temp_sum"]) + temperature
            values["temp_sum_sq"] = float(values["temp_sum_sq"]) + temperature * temperature
            values["temp_max"] = max(float(values["temp_max"]), temperature)
            values["vib_sum"] = float(values["vib_sum"]) + vibration
            values["load_sum"] = float(values["load_sum"]) + load
            values["anomalies"] = int(values["anomalies"]) + int(row["scenario"] != "normal_operation")
    maintenance = _event_counts(data_dir / "raw" / "files" / "maintenance.csv", "machine_id")
    failures = _event_counts(data_dir / "raw" / "files" / "failures.json", "machine_id")
    metrics: list[dict[str, object]] = []
    for machine_id, values in sorted(accumulators.items()):
        count = int(values["count"])
        avg_temp = float(values["temp_sum"]) / count
        avg_vibration = float(values["vib_sum"]) / count
        anomaly_rate = int(values["anomalies"]) / count
        risk_score = min(
            1.0,
            max(0.0, (avg_temp - 48) / 24) * 0.32
            + max(0.0, (avg_vibration - 2.3) / 4) * 0.28
            + anomaly_rate * 2.5 * 0.2
            + min(failures.get(machine_id, 0) / 20, 1) * 0.2,
        )
        metrics.append(
            {
                "machine_id": machine_id,
                "measurement_count": count,
                "avg_temperature_c": round(avg_temp, 4),
                "max_temperature_c": round(float(values["temp_max"]), 4),
                "temperature_stddev": round(
                    math.sqrt(max(0.0, float(values["temp_sum_sq"]) / count - avg_temp * avg_temp)), 4
                ),
                "avg_vibration_mm_s": round(avg_vibration, 4),
                "avg_load_pct": round(float(values["load_sum"]) / count, 4),
                "anomaly_rate": round(anomaly_rate, 6),
                "failure_count": failures.get(machine_id, 0),
                "maintenance_count": maintenance.get(machine_id, 0),
                "risk_score": round(risk_score, 6),
                "risk_label": "high" if risk_score >= 0.65 else "medium" if risk_score >= 0.35 else "low",
                "score_method": "transparent-rule-baseline-v1",
            }
        )
    output = data_dir / "processed" / "machine_metrics.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    (data_dir / "processed" / "predictions.json").write_text(
        json.dumps(
            [
                {k: row[k] for k in ("machine_id", "risk_score", "risk_label", "score_method")}
                for row in metrics
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return metrics


def run_local_pipeline(settings: Settings) -> dict[str, object]:
    """Run the dependency-free reference path and persist an auditable summary."""
    start = time.monotonic()
    run_id = f"local-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    generated = IndustrialDataGenerator(settings).generate()
    quality = validate_sensor_file(settings.data_dir)
    metrics = calculate_metrics(settings.data_dir)
    summary: dict[str, object] = {
        "run_id": run_id,
        "status": "success",
        "profile": settings.profile,
        "seed": settings.seed,
        "generated": generated,
        "quality": quality.as_dict(),
        "machines_scored": len(metrics),
        "high_risk_machines": sum(row["risk_label"] == "high" for row in metrics),
        "highest_risk": sorted(metrics, key=lambda row: float(row["risk_score"]), reverse=True)[:5],
        "duration_seconds": round(time.monotonic() - start, 3),
        "limitations": [
            "Local score is an explainable baseline, not the Spark MLlib model.",
            "Database persistence and graph synchronization require the container stack.",
        ],
    }
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "latest_pipeline_run.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary
