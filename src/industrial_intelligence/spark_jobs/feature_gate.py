"""Spark-side analytical feature gate executed before all ML training."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

from industrial_intelligence.ml.classification import ENGINEERED_FEATURES, purged_chronological_split
from industrial_intelligence.quality_contract import EXPECTED_MACHINE_COUNT


def validate_features(data: object) -> dict[str, object]:
    required = set(ENGINEERED_FEATURES + ["machine_id", "metric_date", "risk_label", "machine_type"])
    missing_columns = sorted(required.difference(data.columns))
    if missing_columns:
        raise ValueError(f"Feature quality gate failed: missing columns {missing_columns}")
    rows = data.count()
    machines = data.select("machine_id").distinct().count()
    null_rows = data.filter(
        F.col("machine_id").isNull()
        | F.col("metric_date").isNull()
        | F.col("risk_label").isNull()
        | F.col("machine_type").isNull()
    ).count()
    class_counts = {
        str(int(row["risk_label"])): int(row["count"])
        for row in data.groupBy("risk_label").count().orderBy("risk_label").collect()
    }
    if rows == 0:
        raise ValueError("Feature quality gate failed: empty feature dataset")
    if machines != EXPECTED_MACHINE_COUNT:
        raise ValueError(
            f"Feature quality gate failed: expected {EXPECTED_MACHINE_COUNT} machines, got {machines}"
        )
    if null_rows:
        raise ValueError(f"Feature quality gate failed: {null_rows} incomplete feature rows")
    if set(class_counts) != {"0", "1"}:
        raise ValueError(f"Feature quality gate failed: both target classes are required: {class_counts}")

    split = purged_chronological_split(data)
    split_counts: dict[str, dict[str, int]] = {}
    split_dates: dict[str, set[object]] = {}
    for name, frame in (
        ("train", split.train),
        ("validation", split.validation),
        ("test", split.test),
    ):
        split_counts[name] = {
            str(int(row["risk_label"])): int(row["count"])
            for row in frame.groupBy("risk_label").count().collect()
        }
        if set(split_counts[name]) != {"0", "1"}:
            raise ValueError(
                f"Feature quality gate failed: split {name} lacks a target class: {split_counts[name]}"
            )
        split_dates[name] = {row[0] for row in frame.select("metric_date").distinct().collect()}
    if (
        split_dates["train"] & split_dates["validation"]
        or split_dates["train"] & split_dates["test"]
        or split_dates["validation"] & split_dates["test"]
    ):
        raise ValueError("Feature quality gate failed: temporal split overlap")
    return {
        "gate": "features",
        "status": "passed",
        "feature_rows": rows,
        "machines": machines,
        "class_counts": class_counts,
        "split_class_counts": split_counts,
        "split": split.metadata,
        "null_key_or_target_rows": null_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.getenv("IIP_DATA_DIR", "data"))
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    spark = SparkSession.builder.appName("industrial-feature-quality-gate").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    try:
        data = spark.read.parquet(str(data_dir / "processed" / "spark_features.parquet")).cache()
        report = validate_features(data)
        (data_dir / "processed" / "feature_quality_report.json").write_text(
            json.dumps(report, indent=2, default=str, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(report, indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
