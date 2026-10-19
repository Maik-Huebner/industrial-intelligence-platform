"""Spark feature engineering with joins, SQL, windows, and aggregations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pyspark.sql import SparkSession, Window, functions as F, types as T


def build_features(spark: SparkSession, data_dir: str) -> tuple[object, dict[str, int]]:
    raw = Path(data_dir) / "raw"
    processed = Path(data_dir) / "processed"
    sensors = spark.read.json(str(raw / "mongodb" / "sensor_readings.jsonl"))
    machines = spark.read.option("header", True).option("inferSchema", True).csv(str(raw / "postgres" / "machines.csv"))
    maintenance = spark.read.option("header", True).option("inferSchema", True).csv(str(raw / "files" / "maintenance.csv"))
    failures_schema = T.ArrayType(
        T.StructType(
            [
                T.StructField("failure_id", T.StringType()),
                T.StructField("machine_id", T.StringType()),
                T.StructField("occurred_at", T.StringType()),
                T.StructField("failure_type", T.StringType()),
                T.StructField("severity", T.StringType()),
                T.StructField("downtime_minutes", T.IntegerType()),
            ]
        )
    )
    failures_text = spark.read.text(str(raw / "files" / "failures.json"))
    failures = (
        failures_text.agg(F.concat_ws("", F.collect_list("value")).alias("payload"))
        .select(F.explode(F.from_json("payload", failures_schema)).alias("f"))
        .select("f.*")
    )

    normalized = (
        sensors.select(
            "reading_id",
            "machine_id",
            F.to_timestamp("timestamp").alias("event_ts"),
            F.col("sensors.temperature.value").cast("double").alias("temperature_c"),
            F.col("sensors.vibration.value").cast("double").alias("vibration_mm_s"),
            F.col("sensors.power.value").cast("double").alias("power_kw"),
            F.col("sensors.load.value").cast("double").alias("load_pct"),
            F.col("context.scenario").alias("scenario"),
        )
        .filter(F.col("machine_id").rlike("^M-[0-9]{3}$"))
        .filter(F.col("event_ts").isNotNull())
        .filter(F.col("temperature_c").between(-40, 180))
        .filter(F.col("vibration_mm_s").between(0, 50))
        .filter(F.col("power_kw").between(0, 500))
        .filter(F.col("load_pct").between(0, 100))
        .dropDuplicates(["reading_id"])
        .withColumn("metric_date", F.to_date("event_ts"))
    )

    reading_window = Window.partitionBy("machine_id").orderBy("event_ts")
    rolling_window = reading_window.rowsBetween(-11, 0)
    enriched = (
        normalized.withColumn("previous_temperature_c", F.lag("temperature_c").over(reading_window))
        .withColumn("temperature_delta", F.col("temperature_c") - F.col("previous_temperature_c"))
        .withColumn("rolling_temperature_c", F.avg("temperature_c").over(rolling_window))
        .withColumn("is_anomaly", (F.col("scenario") != "normal_operation").cast("int"))
    )
    daily = enriched.groupBy("machine_id", "metric_date").agg(
        F.count("*").alias("measurement_count"),
        F.avg("temperature_c").alias("avg_temperature_c"),
        F.max("temperature_c").alias("max_temperature_c"),
        F.stddev_pop("temperature_c").alias("temperature_stddev"),
        F.avg("vibration_mm_s").alias("avg_vibration_mm_s"),
        F.max("vibration_mm_s").alias("max_vibration_mm_s"),
        F.avg("power_kw").alias("avg_power_kw"),
        F.avg("load_pct").alias("avg_load_pct"),
        F.avg("is_anomaly").alias("anomaly_rate"),
        F.sum("is_anomaly").alias("anomaly_count"),
    )
    maintenance_daily = maintenance.withColumn("metric_date", F.to_date("performed_at")).groupBy("machine_id", "metric_date").agg(
        F.count("*").alias("maintenance_count"), F.sum("duration_minutes").alias("maintenance_minutes")
    )
    failure_daily = failures.withColumn("metric_date", F.to_date("occurred_at")).groupBy("machine_id", "metric_date").agg(
        F.count("*").alias("failure_count"), F.sum("downtime_minutes").alias("downtime_minutes")
    )
    joined = (
        daily.join(machines, "machine_id", "inner")
        .join(maintenance_daily, ["machine_id", "metric_date"], "left")
        .join(failure_daily, ["machine_id", "metric_date"], "left")
        .fillna(0, subset=["maintenance_count", "maintenance_minutes", "failure_count", "downtime_minutes"])
        .withColumn("machine_age_years", F.lit(2026) - F.col("installed_year"))
    )
    daily_window = Window.partitionBy("machine_id").orderBy("metric_date")
    prior_week = daily_window.rowsBetween(-7, -1)
    historical = (
        joined.withColumn("previous_avg_temperature_c", F.lag("avg_temperature_c").over(daily_window))
        .withColumn("previous_avg_vibration_mm_s", F.lag("avg_vibration_mm_s").over(daily_window))
        .withColumn("previous_anomaly_rate", F.lag("anomaly_rate").over(daily_window))
        .withColumn("prior_7d_avg_temperature_c", F.avg("avg_temperature_c").over(prior_week))
        .withColumn("prior_7d_temperature_stddev", F.stddev_pop("avg_temperature_c").over(prior_week))
        .withColumn("prior_7d_avg_vibration_mm_s", F.avg("avg_vibration_mm_s").over(prior_week))
        .withColumn("prior_7d_anomaly_rate", F.avg("anomaly_rate").over(prior_week))
        .withColumn(
            "temperature_change_1d",
            F.col("avg_temperature_c")
            - F.coalesce(F.col("previous_avg_temperature_c"), F.col("avg_temperature_c")),
        )
        .withColumn(
            "vibration_change_1d",
            F.col("avg_vibration_mm_s")
            - F.coalesce(F.col("previous_avg_vibration_mm_s"), F.col("avg_vibration_mm_s")),
        )
        .withColumn(
            "temperature_deviation_7d",
            F.col("avg_temperature_c")
            - F.coalesce(F.col("prior_7d_avg_temperature_c"), F.col("avg_temperature_c")),
        )
        .withColumn(
            "vibration_deviation_7d",
            F.col("avg_vibration_mm_s")
            - F.coalesce(F.col("prior_7d_avg_vibration_mm_s"), F.col("avg_vibration_mm_s")),
        )
        .withColumn(
            "anomaly_rate_deviation_7d",
            F.col("anomaly_rate")
            - F.coalesce(F.col("prior_7d_anomaly_rate"), F.col("anomaly_rate")),
        )
        .withColumn(
            "prior_7d_avg_temperature_c",
            F.coalesce(F.col("prior_7d_avg_temperature_c"), F.col("avg_temperature_c")),
        )
        .withColumn(
            "prior_7d_avg_vibration_mm_s",
            F.coalesce(F.col("prior_7d_avg_vibration_mm_s"), F.col("avg_vibration_mm_s")),
        )
        .withColumn(
            "prior_7d_anomaly_rate",
            F.coalesce(F.col("prior_7d_anomaly_rate"), F.col("anomaly_rate")),
        )
        .withColumn("day_of_week", F.dayofweek("metric_date").cast("double"))
        .withColumn("day_of_week_sin", F.sin(2 * F.lit(3.141592653589793) * (F.col("day_of_week") - 1) / 7))
        .withColumn("day_of_week_cos", F.cos(2 * F.lit(3.141592653589793) * (F.col("day_of_week") - 1) / 7))
        .fillna(
            0.0,
            subset=[
                "prior_7d_temperature_stddev",
                "temperature_change_1d",
                "vibration_change_1d",
                "temperature_deviation_7d",
                "vibration_deviation_7d",
                "anomaly_rate_deviation_7d",
            ],
        )
    )
    future_window = Window.partitionBy("machine_id").orderBy("metric_date")
    features = (
        historical.withColumn("future_avg_temperature_c", F.lead("avg_temperature_c").over(future_window))
        .withColumn("future_failure_count", F.lead("failure_count").over(future_window))
        .withColumn("future_anomaly_rate", F.lead("anomaly_rate").over(future_window))
        .withColumn("future_max_vibration_mm_s", F.lead("max_vibration_mm_s").over(future_window))
        .withColumn(
            "risk_label",
            (
                (F.coalesce(F.col("future_failure_count"), F.lit(0)) > 0)
                | (F.col("future_anomaly_rate") > 0.08)
                | (F.col("future_max_vibration_mm_s") > 7.5)
            ).cast("double"),
        )
        .withColumn("risk_rank", F.dense_rank().over(Window.partitionBy("metric_date").orderBy(F.desc("anomaly_rate"), F.desc("max_vibration_mm_s"))))
        .filter(F.col("future_avg_temperature_c").isNotNull())
    )

    features.createOrReplaceTempView("machine_features")
    spark.sql(
        """
        SELECT line_id, metric_date, COUNT(*) AS machines,
               AVG(avg_temperature_c) AS line_avg_temperature,
               MAX(max_vibration_mm_s) AS line_max_vibration,
               SUM(failure_count) AS line_failures
        FROM machine_features
        GROUP BY line_id, metric_date
        HAVING COUNT(*) > 0
        ORDER BY metric_date, line_id
        """
    ).write.mode("overwrite").parquet(str(processed / "line_daily_metrics.parquet"))
    features.orderBy("machine_id", "metric_date").write.mode("overwrite").partitionBy("metric_date").parquet(
        str(processed / "spark_features.parquet")
    )
    evidence = {
        "input_rows": sensors.count(),
        "valid_rows": normalized.count(),
        "feature_rows": features.count(),
        "machines": features.select("machine_id").distinct().count(),
    }
    return features, evidence


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--data-dir", default=os.getenv("IIP_DATA_DIR", "data"))
    args = argument_parser.parse_args()
    spark = SparkSession.builder.appName("industrial-feature-engineering").getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    try:
        _, evidence = build_features(spark, args.data_dir)
        print(evidence)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
