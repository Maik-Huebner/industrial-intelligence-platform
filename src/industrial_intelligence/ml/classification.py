"""Leakage-aware Spark ML classification benchmark."""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from typing import Any

from pyspark.ml import Pipeline
from pyspark.ml.classification import (
    DecisionTreeClassifier,
    GBTClassifier,
    LogisticRegression,
    RandomForestClassifier,
)
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import OneHotEncoder, StandardScaler, StringIndexer, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F

from .metrics import binary_metrics, optimize_threshold

BASE_FEATURES = [
    "avg_temperature_c",
    "temperature_stddev",
    "avg_vibration_mm_s",
    "max_vibration_mm_s",
    "avg_power_kw",
    "avg_load_pct",
    "anomaly_rate",
    "machine_age_years",
    "criticality",
    "maintenance_count",
]

ENGINEERED_FEATURES = BASE_FEATURES + [
    "prior_7d_avg_temperature_c",
    "prior_7d_temperature_stddev",
    "prior_7d_avg_vibration_mm_s",
    "prior_7d_anomaly_rate",
    "temperature_change_1d",
    "vibration_change_1d",
    "temperature_deviation_7d",
    "vibration_deviation_7d",
    "anomaly_rate_deviation_7d",
    "day_of_week_sin",
    "day_of_week_cos",
]


@dataclass(frozen=True)
class SplitResult:
    train: Any
    validation: Any
    test: Any
    metadata: dict[str, object]


def purged_chronological_split(data: Any) -> SplitResult:
    """Split by date and purge one label-horizon day between each partition."""
    dates = [row[0] for row in data.select("metric_date").distinct().orderBy("metric_date").collect()]
    if len(dates) < 12:
        raise ValueError("At least 12 distinct dates are required for a purged temporal split")
    train_size = int(len(dates) * 0.6)
    remaining = len(dates) - train_size - 2
    validation_size = remaining // 2
    train_dates = dates[:train_size]
    purge_after_train = dates[train_size]
    validation_dates = dates[train_size + 1 : train_size + 1 + validation_size]
    purge_after_validation = dates[train_size + 1 + validation_size]
    test_dates = dates[train_size + 2 + validation_size :]
    return SplitResult(
        train=data.filter(F.col("metric_date").isin(train_dates)),
        validation=data.filter(F.col("metric_date").isin(validation_dates)),
        test=data.filter(F.col("metric_date").isin(test_dates)),
        metadata={
            "strategy": "purged_chronological_60_20_20",
            "target_horizon_days": 1,
            "train": [str(train_dates[0]), str(train_dates[-1])],
            "purge_after_train": str(purge_after_train),
            "validation": [str(validation_dates[0]), str(validation_dates[-1])],
            "purge_after_validation": str(purge_after_validation),
            "test": [str(test_dates[0]), str(test_dates[-1])],
            "rationale": "Future prediction for already-known machines; one day is purged at each boundary because the label uses lead(1).",
        },
    )


def _class_counts(frame: Any) -> dict[str, int]:
    return {
        str(int(row["risk_label"])): int(row["count"])
        for row in frame.groupBy("risk_label").count().orderBy("risk_label").collect()
    }


def _with_class_weights(train: Any) -> tuple[Any, dict[str, float]]:
    counts = _class_counts(train)
    total = sum(counts.values())
    weights = {label: total / (2 * count) for label, count in counts.items()}
    weighted = train.withColumn(
        "class_weight",
        F.when(F.col("risk_label") == 0, F.lit(weights["0"])).otherwise(F.lit(weights["1"])),
    )
    return weighted, weights


def _pipeline(estimator: Any, features: list[str], scale: bool) -> Pipeline:
    indexer = StringIndexer(
        inputCol="machine_type",
        outputCol="machine_type_index",
        handleInvalid="keep",
        stringOrderType="alphabetAsc",
    )
    encoder = OneHotEncoder(
        inputCols=["machine_type_index"],
        outputCols=["machine_type_ohe"],
        handleInvalid="keep",
        dropLast=False,
    )
    vector_column = "unscaled_features" if scale else "features"
    assembler = VectorAssembler(
        inputCols=features + ["machine_type_ohe"],
        outputCol=vector_column,
        handleInvalid="error",
    )
    stages: list[Any] = [indexer, encoder, assembler]
    if scale:
        stages.append(StandardScaler(inputCol=vector_column, outputCol="features", withStd=True, withMean=True))
    stages.append(estimator)
    return Pipeline(stages=stages)


def _candidate_estimators(model_name: str) -> list[tuple[dict[str, object], Any, bool]]:
    if model_name == "logistic_regression":
        return [
            (
                {"regParam": reg_param, "elasticNetParam": elastic_net},
                LogisticRegression(
                    labelCol="risk_label",
                    featuresCol="features",
                    weightCol="class_weight",
                    maxIter=120,
                    regParam=reg_param,
                    elasticNetParam=elastic_net,
                ),
                True,
            )
            for reg_param, elastic_net in ((0.01, 0.0), (0.05, 0.5))
        ]
    if model_name == "decision_tree":
        return [
            (
                {"maxDepth": depth, "minInstancesPerNode": minimum},
                DecisionTreeClassifier(
                    labelCol="risk_label",
                    featuresCol="features",
                    weightCol="class_weight",
                    maxDepth=depth,
                    minInstancesPerNode=minimum,
                    seed=42,
                ),
                False,
            )
            for depth, minimum in ((4, 20), (8, 5))
        ]
    if model_name == "random_forest":
        return [
            (
                {"numTrees": trees, "maxDepth": depth},
                RandomForestClassifier(
                    labelCol="risk_label",
                    featuresCol="features",
                    weightCol="class_weight",
                    numTrees=trees,
                    maxDepth=depth,
                    featureSubsetStrategy="sqrt",
                    seed=42,
                ),
                False,
            )
            for trees, depth in ((30, 5),)
        ]
    if model_name == "gradient_boosted_trees":
        return [
            (
                {"maxIter": iterations, "maxDepth": depth},
                GBTClassifier(
                    labelCol="risk_label",
                    featuresCol="features",
                    weightCol="class_weight",
                    maxIter=iterations,
                    maxDepth=depth,
                    stepSize=0.08,
                    seed=42,
                ),
                False,
            )
            for iterations, depth in ((20, 3),)
        ]
    raise ValueError(f"Unsupported model: {model_name}")


def _probability_rows(predictions: Any) -> tuple[list[int], list[float]]:
    rows = (
        predictions.orderBy("metric_date", "machine_id").select(
            F.col("risk_label").cast("int").alias("label"),
            vector_to_array("probability")[1].alias("probability"),
        )
        .collect()
    )
    return [int(row["label"]) for row in rows], [float(row["probability"]) for row in rows]


def _evaluate(predictions: Any, threshold: float) -> tuple[dict[str, object], Any]:
    scored = (
        predictions.withColumn("risk_probability", vector_to_array("probability")[1])
        .withColumn("prediction", (F.col("risk_probability") >= F.lit(threshold)).cast("double"))
    )
    rows = scored.select("risk_label", "prediction").collect()
    metrics = binary_metrics(
        [int(row["risk_label"]) for row in rows],
        [int(row["prediction"]) for row in rows],
    )
    evaluator = BinaryClassificationEvaluator(labelCol="risk_label", rawPredictionCol="probability")
    metrics["roc_auc"] = float(evaluator.setMetricName("areaUnderROC").evaluate(scored))
    metrics["pr_auc"] = float(evaluator.setMetricName("areaUnderPR").evaluate(scored))
    return metrics, scored


def _feature_importance(model: Any, features: list[str]) -> list[dict[str, object]]:
    estimator_model = model.stages[-1]
    if not hasattr(estimator_model, "featureImportances"):
        return []
    values = list(map(float, estimator_model.featureImportances))
    names = features + [f"machine_type_ohe_{index}" for index in range(max(0, len(values) - len(features)))]
    ranked = sorted(zip(names, values, strict=False), key=lambda pair: pair[1], reverse=True)
    return [{"feature": name, "importance": value} for name, value in ranked[:15]]


def _train_tuned_model(
    model_name: str,
    train: Any,
    validation: Any,
    test: Any,
    features: list[str],
) -> dict[str, object]:
    best: dict[str, object] | None = None
    candidate_summaries = []
    total_tuning_seconds = 0.0
    for parameters, estimator, scale in _candidate_estimators(model_name):
        started = time.perf_counter()
        model = _pipeline(estimator, features, scale).fit(train)
        training_seconds = time.perf_counter() - started
        total_tuning_seconds += training_seconds
        validation_predictions = model.transform(validation)
        labels, probabilities = _probability_rows(validation_predictions)
        threshold_result = optimize_threshold(labels, probabilities)
        validation_metrics, _ = _evaluate(validation_predictions, threshold_result["threshold"])
        candidate = {
            "parameters": parameters,
            "model": model,
            "threshold": threshold_result["threshold"],
            "validation_metrics": validation_metrics,
            "training_seconds": training_seconds,
            "scale_numeric_features": scale,
        }
        candidate_summaries.append(
            {
                "parameters": parameters,
                "threshold": threshold_result["threshold"],
                "macro_f1": validation_metrics["macro_f1"],
                "balanced_accuracy": validation_metrics["balanced_accuracy"],
                "training_seconds": training_seconds,
            }
        )
        if best is None or (
            validation_metrics["macro_f1"], validation_metrics["balanced_accuracy"]
        ) > (
            best["validation_metrics"]["macro_f1"],
            best["validation_metrics"]["balanced_accuracy"],
        ):
            if best is not None:
                del best["model"]
            best = candidate
        else:
            del model
        gc.collect()
    assert best is not None
    test_metrics, test_predictions = _evaluate(best["model"].transform(test), best["threshold"])
    report = {
        "parameters": best["parameters"],
        "threshold": best["threshold"],
        "class_weighting": "inverse_frequency_from_training_only",
        "scale_numeric_features": best["scale_numeric_features"],
        "training_seconds": best["training_seconds"],
        "tuning_seconds": total_tuning_seconds,
        "validation": best["validation_metrics"],
        "test": test_metrics,
        "feature_importance": _feature_importance(best["model"], features),
        "candidates": candidate_summaries,
    }
    del test_predictions
    del best["model"]
    gc.collect()
    return report


def _fit_locked_model(
    model_name: str,
    train: Any,
    test: Any,
    features: list[str],
    parameters: dict[str, object],
    threshold: float,
) -> tuple[Any, Any, dict[str, object], float]:
    match = next(
        (candidate for candidate in _candidate_estimators(model_name) if candidate[0] == parameters),
        None,
    )
    if match is None:
        raise ValueError(f"Locked parameters not found for {model_name}: {parameters}")
    _, estimator, scale = match
    started = time.perf_counter()
    model = _pipeline(estimator, features, scale).fit(train)
    training_seconds = time.perf_counter() - started
    test_metrics, test_predictions = _evaluate(model.transform(test), threshold)
    return model, test_predictions, test_metrics, training_seconds


def _dummy_report(train: Any, validation: Any, test: Any) -> dict[str, object]:
    counts = _class_counts(train)
    majority = max(counts, key=counts.get)

    def evaluate(frame: Any) -> dict[str, object]:
        labels = [int(row["risk_label"]) for row in frame.select("risk_label").collect()]
        predictions = [int(majority)] * len(labels)
        metrics = binary_metrics(labels, predictions)
        metrics["roc_auc"] = 0.5
        metrics["pr_auc"] = sum(labels) / len(labels)
        return metrics

    return {
        "parameters": {"strategy": "training_majority", "constant_prediction": int(majority)},
        "threshold": None,
        "class_weighting": "none",
        "scale_numeric_features": False,
        "training_seconds": 0.0,
        "tuning_seconds": 0.0,
        "validation": evaluate(validation),
        "test": evaluate(test),
        "feature_importance": [],
    }


def run_classification_benchmark(data: Any) -> tuple[dict[str, object], Any, Any]:
    split = purged_chronological_split(data)
    train, class_weights = _with_class_weights(split.train.cache())
    validation = split.validation.cache()
    test = split.test.cache()
    models: dict[str, dict[str, object]] = {"dummy_majority": _dummy_report(train, validation, test)}
    for model_name in ("logistic_regression", "decision_tree", "random_forest", "gradient_boosted_trees"):
        model_report = _train_tuned_model(
            model_name, train, validation, test, ENGINEERED_FEATURES
        )
        models[model_name] = model_report

    base_report = _train_tuned_model(
        "logistic_regression", train, validation, test, BASE_FEATURES
    )
    eligible = [
        name
        for name in models
        if name != "dummy_majority"
        if all(models[name]["validation"]["prediction_counts"][label] > 0 for label in ("0", "1"))
    ]
    selected_name = max(
        eligible,
        key=lambda name: (
            models[name]["validation"]["macro_f1"],
            models[name]["validation"]["balanced_accuracy"],
        ),
    )
    combined_train, combined_weights = _with_class_weights(split.train.unionByName(validation).cache())
    final_model, final_predictions, final_test_metrics, final_training_seconds = _fit_locked_model(
        selected_name,
        combined_train,
        test,
        ENGINEERED_FEATURES,
        models[selected_name]["parameters"],
        models[selected_name]["threshold"],
    )
    report = {
        "split": split.metadata,
        "counts": {
            "all": int(data.count()),
            "train": int(train.count()),
            "validation": int(validation.count()),
            "test": int(test.count()),
        },
        "class_distribution": {
            "all": _class_counts(data),
            "train": _class_counts(train),
            "validation": _class_counts(validation),
            "test": _class_counts(test),
        },
        "class_weights": class_weights,
        "features": ENGINEERED_FEATURES + ["machine_type via one-hot encoding"],
        "excluded_as_target_leakage": [
            "future_avg_temperature_c",
            "future_failure_count",
            "future_anomaly_rate",
            "future_max_vibration_mm_s",
            "risk_rank",
        ],
        "pressure_feature": "not_available_in_source_schema",
        "feature_ablation": {
            "base_logistic_validation": base_report["validation"],
            "engineered_logistic_validation": models["logistic_regression"]["validation"],
        },
        "models": models,
        "selection_rule": "highest validation macro-F1, then balanced accuracy; both classes must be predicted",
        "selected_model": selected_name,
        "selected_threshold": models[selected_name]["threshold"],
        "final_refit": {
            "training_data": "train_plus_validation_after_model_and_threshold_lock",
            "class_weights": combined_weights,
            "training_seconds": final_training_seconds,
            "test": final_test_metrics,
        },
        "test_was_used_for_selection": False,
    }
    return report, final_model, final_predictions
