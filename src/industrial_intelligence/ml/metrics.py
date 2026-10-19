"""Dependency-free binary metrics used by the Spark benchmark and unit tests."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def binary_metrics(labels: Iterable[int], predictions: Iterable[int]) -> dict[str, object]:
    """Calculate class-specific metrics from binary labels and predictions."""
    pairs = [(int(label), int(prediction)) for label, prediction in zip(labels, predictions, strict=True)]
    tn = sum(label == 0 and prediction == 0 for label, prediction in pairs)
    fp = sum(label == 0 and prediction == 1 for label, prediction in pairs)
    fn = sum(label == 1 and prediction == 0 for label, prediction in pairs)
    tp = sum(label == 1 and prediction == 1 for label, prediction in pairs)

    precision_0 = _safe_ratio(tn, tn + fn)
    recall_0 = _safe_ratio(tn, tn + fp)
    precision_1 = _safe_ratio(tp, tp + fp)
    recall_1 = _safe_ratio(tp, tp + fn)
    f1_0 = _safe_ratio(2 * precision_0 * recall_0, precision_0 + recall_0)
    f1_1 = _safe_ratio(2 * precision_1 * recall_1, precision_1 + recall_1)
    support_0 = tn + fp
    support_1 = tp + fn
    total = support_0 + support_1
    return {
        "accuracy": _safe_ratio(tp + tn, total),
        "macro_f1": (f1_0 + f1_1) / 2,
        "weighted_f1": _safe_ratio(f1_0 * support_0 + f1_1 * support_1, total),
        "balanced_accuracy": (recall_0 + recall_1) / 2,
        "per_class": {
            "0": {"precision": precision_0, "recall": recall_0, "f1": f1_0, "support": support_0},
            "1": {"precision": precision_1, "recall": recall_1, "f1": f1_1, "support": support_1},
        },
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "prediction_counts": {"0": tn + fn, "1": fp + tp},
    }


def optimize_threshold(
    labels: Sequence[int],
    probabilities: Sequence[float],
    thresholds: Sequence[float] | None = None,
) -> dict[str, object]:
    """Choose a threshold by macro-F1, then balanced accuracy, on validation data only."""
    if len(labels) != len(probabilities) or not labels:
        raise ValueError("labels and probabilities must be non-empty and have equal length")
    candidates = thresholds or tuple(value / 100 for value in range(20, 81, 2))
    results = []
    for threshold in candidates:
        predictions = [int(probability >= threshold) for probability in probabilities]
        metrics = binary_metrics(labels, predictions)
        results.append((metrics["macro_f1"], metrics["balanced_accuracy"], -abs(threshold - 0.5), threshold, metrics))
    _, _, _, threshold, metrics = max(results, key=lambda item: item[:3])
    return {"threshold": float(threshold), "metrics": metrics}
