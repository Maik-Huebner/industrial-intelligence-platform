import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_beats_majority_and_predicts_both_classes() -> None:
    report = json.loads((PROJECT_ROOT / "reports/classification_benchmark.json").read_text())
    baseline = report["models"]["dummy_majority"]["test"]
    final = report["final_refit"]["test"]
    assert report["test_was_used_for_selection"] is False
    assert final["macro_f1"] > baseline["macro_f1"]
    assert final["balanced_accuracy"] > baseline["balanced_accuracy"]
    assert final["prediction_counts"]["0"] > 0
    assert final["prediction_counts"]["1"] > 0


def test_future_target_columns_are_excluded_from_features() -> None:
    report = json.loads((PROJECT_ROOT / "reports/classification_benchmark.json").read_text())
    feature_names = " ".join(report["features"])
    assert "future_" not in feature_names
    assert "risk_label" not in feature_names
    assert set(report["excluded_as_target_leakage"]) >= {
        "future_failure_count",
        "future_anomaly_rate",
        "future_max_vibration_mm_s",
    }
