"""Audit the existing classification dataset without training or mutating it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

from industrial_intelligence.ml.classification import ENGINEERED_FEATURES, purged_chronological_split


def class_counts(frame: object) -> dict[str, int]:
    return {
        str(int(row["risk_label"])): int(row["count"])
        for row in frame.groupBy("risk_label").count().orderBy("risk_label").collect()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="reports/classification_data_audit.json")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("classification-data-audit").getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    try:
        data = spark.read.parquet(str(Path(args.data_dir) / "processed" / "spark_features.parquet")).cache()
        dates = [row[0] for row in data.select("metric_date").distinct().orderBy("metric_date").collect()]
        split = purged_chronological_split(data)
        splits = {
            "train": split.train,
            "validation": split.validation,
            "test": split.test,
        }

        target_components = {
            "next_day_failure": F.col("future_failure_count") > 0,
            "next_day_anomaly_rate": F.col("future_anomaly_rate") > 0.08,
            "next_day_max_vibration": F.col("future_max_vibration_mm_s") > 7.5,
        }
        component_counts = {
            name: int(data.filter(condition).count()) for name, condition in target_components.items()
        }
        component_counts["positive_union"] = int(data.filter(F.col("risk_label") == 1).count())
        component_counts["next_day_max_vibration_only"] = int(
            data.filter(
                target_components["next_day_max_vibration"]
                & ~target_components["next_day_failure"]
                & ~target_components["next_day_anomaly_rate"]
            ).count()
        )

        numeric_columns = ENGINEERED_FEATURES + ["failure_count"]
        correlations = {
            column: data.stat.corr(column, "risk_label") for column in numeric_columns
        }
        monthly = [
            {
                "month": str(row["month"]),
                "label": int(row["risk_label"]),
                "count": int(row["count"]),
            }
            for row in (
                data.withColumn("month", F.date_format("metric_date", "yyyy-MM"))
                .groupBy("month", "risk_label")
                .count()
                .orderBy("month", "risk_label")
                .collect()
            )
        ]
        report = {
            "row_count": int(data.count()),
            "date_range": [str(dates[0]), str(dates[-1])],
            "split": split.metadata,
            "class_distribution": {
                name: {"rows": int(frame.count()), "classes": class_counts(frame)}
                for name, frame in splits.items()
            },
            "target_component_counts": component_counts,
            "feature_target_pearson_correlations": correlations,
            "monthly_class_distribution": monthly,
            "pressure_feature_available": False,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
