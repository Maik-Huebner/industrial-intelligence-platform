import pytest

from industrial_intelligence.ml.metrics import binary_metrics, optimize_threshold


def test_binary_metrics_reports_each_class_and_balanced_accuracy() -> None:
    metrics = binary_metrics([0, 0, 1, 1], [0, 1, 0, 1])
    assert metrics["accuracy"] == 0.5
    assert metrics["balanced_accuracy"] == 0.5
    assert metrics["macro_f1"] == 0.5
    assert metrics["per_class"]["0"]["recall"] == 0.5
    assert metrics["per_class"]["1"]["recall"] == 0.5
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 1}


def test_majority_only_prediction_is_not_hidden_by_accuracy() -> None:
    metrics = binary_metrics([0, 1, 1, 1], [1, 1, 1, 1])
    assert metrics["accuracy"] == 0.75
    assert metrics["balanced_accuracy"] == 0.5
    assert metrics["per_class"]["0"]["recall"] == 0.0
    assert metrics["prediction_counts"] == {"0": 0, "1": 4}


def test_threshold_is_chosen_by_validation_macro_f1() -> None:
    result = optimize_threshold(
        [0, 0, 1, 1],
        [0.2, 0.25, 0.45, 0.8],
        thresholds=[0.3, 0.5],
    )
    assert result["threshold"] == pytest.approx(0.3)
    assert result["metrics"]["macro_f1"] == pytest.approx(1.0)


def test_threshold_rejects_mismatched_inputs() -> None:
    with pytest.raises(ValueError):
        optimize_threshold([0], [])
