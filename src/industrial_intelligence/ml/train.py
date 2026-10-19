"""Train classification, regression, and clustering models with MLlib."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier, LogisticRegression
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator, MulticlassClassificationEvaluator, RegressionEvaluator
from pyspark.ml.feature import StandardScaler, StringIndexer, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.ml.regression import LinearRegression
from pyspark.sql import SparkSession, functions as F

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


def split_by_time(data: object) -> tuple[object, object, str]:
    dates = [row[0] for row in data.select("metric_date").distinct().orderBy("metric_date").collect()]
    cutoff = dates[max(1, int(len(dates) * 0.8)) - 1]
    return data.filter(F.col("metric_date") <= cutoff), data.filter(F.col("metric_date") > cutoff), str(cutoff)


def classification_report(train: object, test: object) -> tuple[dict[str, object], object, object, object]:
    indexer = StringIndexer(inputCol="machine_type", outputCol="machine_type_index", handleInvalid="keep")
    assembler = VectorAssembler(inputCols=NUMERIC_FEATURES + ["machine_type_index"], outputCol="unscaled_features", handleInvalid="skip")
    scaler = StandardScaler(inputCol="unscaled_features", outputCol="features", withStd=True, withMean=True)
    logistic = Pipeline(stages=[indexer, assembler, scaler, LogisticRegression(labelCol="risk_label", maxIter=80, regParam=0.05)])
    tree = Pipeline(stages=[indexer, assembler, DecisionTreeClassifier(labelCol="risk_label", featuresCol="unscaled_features", maxDepth=6, seed=42)])
    logistic_model = logistic.fit(train)
    tree_model = tree.fit(train)
    predictions = logistic_model.transform(test)
    tree_predictions = tree_model.transform(test)
    metrics = {}
    for metric_name, evaluator_name in (
        ("accuracy", "accuracy"),
        ("precision", "weightedPrecision"),
        ("recall", "weightedRecall"),
        ("f1", "f1"),
    ):
        evaluator = MulticlassClassificationEvaluator(labelCol="risk_label", predictionCol="prediction", metricName=evaluator_name)
        metrics[metric_name] = evaluator.evaluate(predictions)
        metrics[f"decision_tree_{metric_name}"] = evaluator.evaluate(tree_predictions)
    confusion = [
        {"actual": row["risk_label"], "predicted": row["prediction"], "count": row["count"]}
        for row in predictions.groupBy("risk_label", "prediction").count().orderBy("risk_label", "prediction").collect()
    ]
    return {"metrics": metrics, "confusion_matrix": confusion}, logistic_model, tree_model, predictions


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
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    data_dir = Path(args.data_dir)
    try:
        data = spark.read.parquet(str(data_dir / "processed" / "spark_features.parquet")).cache()
        train, test, cutoff = split_by_time(data)
        # The random split is retained as a course demonstration, not used for reported metrics.
        random_train, random_test = data.randomSplit([0.8, 0.2], seed=42)
        classification, logistic_model, tree_model, class_predictions = classification_report(train, test)
        regression, regression_model = regression_report(train, test)
        clustering, clustering_model = clustering_report(train)
        class_balance = {str(row["risk_label"]): row["count"] for row in data.groupBy("risk_label").count().collect()}
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "validation": {"strategy": "chronological_holdout", "cutoff": cutoff, "random_split_demonstration": [random_train.count(), random_test.count()]},
            "counts": {"all": data.count(), "train": train.count(), "test": test.count()},
            "features": NUMERIC_FEATURES + ["machine_type via StringIndexer for classification"],
            "class_balance": class_balance,
            "classification": classification,
            "regression": regression,
            "clustering": clustering,
            "limitations": [
                "All training data is synthetic and does not establish real-world maintenance performance.",
                "The label uses simulated next-day outcomes and anomaly thresholds.",
                "Linear regression cannot model every nonlinear thermal relationship.",
                "Cluster names require engineering interpretation after profile review.",
            ],
        }
        project_root = data_dir.parent
        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)
        (reports_dir / "ml_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        (
            class_predictions.select(
                "machine_id",
                F.col("metric_date").cast("string").alias("prediction_date"),
                vector_to_array("probability")[1].alias("risk_probability"),
                F.col("prediction").cast("int").alias("predicted_label"),
            )
            .withColumn("model_name", F.lit("logistic_regression"))
            .withColumn("model_version", F.lit("synthetic-v1"))
            .coalesce(1)
            .write.mode("overwrite")
            .json(str(data_dir / "processed" / "ml_predictions_json"))
        )
        model_dir = project_root / "models"
        model_dir.mkdir(exist_ok=True)
        logistic_model.write().overwrite().save(str(model_dir / "logistic_pipeline.model"))
        tree_model.write().overwrite().save(str(model_dir / "decision_tree_pipeline.model"))
        regression_model.write().overwrite().save(str(model_dir / "linear_regression_pipeline.model"))
        clustering_model.write().overwrite().save(str(model_dir / "kmeans_pipeline.model"))
        print(json.dumps(report, indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
