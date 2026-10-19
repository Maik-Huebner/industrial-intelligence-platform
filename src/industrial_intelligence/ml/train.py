"""Train classification, regression, and clustering models with MLlib."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator, RegressionEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql import SparkSession, functions as F

from industrial_intelligence.ml.classification import run_classification_benchmark

NUMERIC_FEATURES = [
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


def split_by_time(data: object) -> tuple[object, object, dict[str, object]]:
    """Create an 80/20 holdout with a one-day purge for lead(1) targets."""
    dates = [row[0] for row in data.select("metric_date").distinct().orderBy("metric_date").collect()]
    if len(dates) < 3:
        raise ValueError("At least three feature dates are required for a purged time split")
    purge_index = min(max(1, int(len(dates) * 0.8) - 1), len(dates) - 2)
    purge_date = dates[purge_index]
    train = data.filter(F.col("metric_date") < purge_date)
    test = data.filter(F.col("metric_date") > purge_date)
    metadata = {
        "strategy": "purged_chronological_80_20",
        "purge_date": str(purge_date),
        "target_horizon_days": 1,
        "rationale": "The lead(1) regression target must not cross the train/test boundary.",
    }
    return train, test, metadata


def regression_report(train: object, test: object) -> tuple[dict[str, float], object]:
    assembler = VectorAssembler(inputCols=NUMERIC_FEATURES, outputCol="features", handleInvalid="skip")
    pipeline = Pipeline(stages=[assembler, LinearRegression(labelCol="future_avg_temperature_c", maxIter=100, regParam=0.05)])
    model = pipeline.fit(train)
    predictions = model.transform(test)
    rmse = RegressionEvaluator(labelCol="future_avg_temperature_c", metricName="rmse").evaluate(predictions)
    mae = RegressionEvaluator(labelCol="future_avg_temperature_c", metricName="mae").evaluate(predictions)
    baseline_value = train.agg(F.avg("future_avg_temperature_c")).first()[0]
    baseline = test.withColumn("baseline_prediction", F.lit(baseline_value))
    baseline_rmse = RegressionEvaluator(labelCol="future_avg_temperature_c", predictionCol="baseline_prediction", metricName="rmse").evaluate(baseline)
    return {"rmse": rmse, "mae": mae, "baseline_rmse": baseline_rmse}, model


def clustering_report(data: object) -> tuple[dict[str, object], object]:
    assembler = VectorAssembler(inputCols=NUMERIC_FEATURES, outputCol="unscaled_cluster_features", handleInvalid="skip")
    scaler = StandardScaler(inputCol="unscaled_cluster_features", outputCol="features", withStd=True, withMean=True)
    pipeline = Pipeline(stages=[assembler, scaler, KMeans(k=3, seed=42, maxIter=60)])
    model = pipeline.fit(data)
    predictions = model.transform(data)
    silhouette = ClusteringEvaluator().evaluate(predictions)
    distribution = {str(row["prediction"]): row["count"] for row in predictions.groupBy("prediction").count().collect()}
    profiles = [row.asDict(recursive=True) for row in predictions.groupBy("prediction").agg(*[F.avg(name).alias(name) for name in NUMERIC_FEATURES]).orderBy("prediction").collect()]
    centers = [list(map(float, center)) for center in model.stages[-1].clusterCenters()]
    return {"silhouette": silhouette, "distribution": distribution, "profiles": profiles, "scaled_cluster_centers": centers}, model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.getenv("IIP_DATA_DIR", "data"))
    args = parser.parse_args()
    spark = SparkSession.builder.appName("industrial-mllib-training").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    data_dir = Path(args.data_dir)
    try:
        data = spark.read.parquet(str(data_dir / "processed" / "spark_features.parquet")).cache()
        train, test, regression_split = split_by_time(data)
        # The random split is retained as a course demonstration, not used for reported metrics.
        random_train, random_test = data.randomSplit([0.8, 0.2], seed=42)
        classification, best_classifier, class_predictions = run_classification_benchmark(data)
        project_root = data_dir.parent
        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)
        (reports_dir / "classification_benchmark.json").write_text(
            json.dumps(classification, indent=2, default=str), encoding="utf-8"
        )
        print(f"classification benchmark complete: {classification['selected_model']}")
        regression, regression_model = regression_report(train, test)
        print("regression evaluation complete")
        clustering, clustering_model = clustering_report(train)
        print("clustering evaluation complete")
        class_balance = {str(row["risk_label"]): row["count"] for row in data.groupBy("risk_label").count().collect()}
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "validation": {
                "regression_and_clustering": regression_split,
                "random_split_demonstration": [random_train.count(), random_test.count()],
                "random_split_used_for_metrics": False,
            },
            "counts": {"all": data.count(), "train": train.count(), "test": test.count()},
            "features": NUMERIC_FEATURES + ["machine_type via StringIndexer for classification"],
            "class_balance": class_balance,
            "classification": classification,
            "regression": regression,
            "clustering": clustering,
            "limitations": [
                "All training data is synthetic and does not establish real-world maintenance performance.",
                "The label uses simulated next-day outcomes and anomaly thresholds.",
                "Pressure deviations cannot be evaluated because the current source schema has no pressure sensor.",
                "Linear regression cannot model every nonlinear thermal relationship.",
                "Cluster names require engineering interpretation after profile review.",
            ],
        }
        (reports_dir / "ml_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        (
            class_predictions.select(
                "machine_id",
                F.col("metric_date").cast("string").alias("prediction_date"),
                "risk_probability",
                F.col("prediction").cast("int").alias("predicted_label"),
            )
            .withColumn("model_name", F.lit(classification["selected_model"]))
            .withColumn("model_version", F.lit("synthetic-v2-classification-benchmark"))
            .coalesce(1)
            .write.mode("overwrite")
            .json(str(data_dir / "processed" / "ml_predictions_json"))
        )
        model_dir = project_root / "models"
        model_dir.mkdir(exist_ok=True)
        best_classifier.write().overwrite().save(str(model_dir / "classification_best_pipeline.model"))
        regression_model.write().overwrite().save(str(model_dir / "linear_regression_pipeline.model"))
        clustering_model.write().overwrite().save(str(model_dir / "kmeans_pipeline.model"))
        print(json.dumps(report, indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
