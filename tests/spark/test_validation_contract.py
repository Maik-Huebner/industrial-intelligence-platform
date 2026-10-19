import pytest

from industrial_intelligence.quality import flatten_document, validation_errors


@pytest.mark.spark
def test_python_and_spark_accept_the_same_range_boundaries() -> None:
    pyspark = pytest.importorskip("pyspark")
    from industrial_intelligence.spark_jobs.transform import normalize_sensor_rows

    spark = pyspark.sql.SparkSession.builder.master("local[1]").appName("contract-test").getOrCreate()
    try:
        documents = [
            {
                "reading_id": "R-valid",
                "machine_id": "M-001",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "sensors": {
                    "temperature": {"value": -40.0},
                    "vibration": {"value": 50.0},
                    "power": {"value": 500.0},
                    "load": {"value": 0.0},
                },
                "context": {"scenario": "normal_operation"},
            },
            {
                "reading_id": "R-invalid",
                "machine_id": "M-001",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "sensors": {
                    "temperature": {"value": 180.1},
                    "vibration": {"value": 1.0},
                    "power": {"value": 10.0},
                    "load": {"value": 50.0},
                },
                "context": {"scenario": "normal_operation"},
            },
        ]
        python_valid = [
            row["reading_id"]
            for row in documents
            if not validation_errors(flatten_document(row), {"M-001"})
        ]
        spark_valid = [
            row["reading_id"]
            for row in normalize_sensor_rows(
                spark.createDataFrame(documents),
                spark.createDataFrame([{"machine_id": "M-001"}]),
            ).select("reading_id").collect()
        ]
        assert spark_valid == python_valid == ["R-valid"]
    finally:
        spark.stop()
