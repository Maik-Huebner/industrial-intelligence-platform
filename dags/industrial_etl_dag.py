"""Airflow orchestration for the industrial ETL and ML workflow.

Large datasets stay on the shared data volume. XCom receives only compact
metadata from the validation task.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

DATA_DIR = Path(os.getenv("IIP_DATA_DIR", "/opt/iip/data"))


def _run(*args: str) -> None:
    process = subprocess.run(args, check=False, text=True, capture_output=True)
    if process.returncode:
        raise AirflowException(f"Command failed ({process.returncode}): {process.stderr[-3000:]}")


@dag(
    dag_id="industrial_etl",
    description="Generate, validate, transform, train, and publish industrial maintenance results",
    schedule="0 2 * * *",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-engineering", "retries": 2, "retry_delay": timedelta(minutes=3), "execution_timeout": timedelta(hours=2)},
    tags=["industrial", "spark", "predictive-maintenance"],
)
def industrial_etl():
    @task(task_id="validate_sources")
    def validate_sources() -> dict[str, object]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return {"data_dir": str(DATA_DIR), "profile": os.getenv("IIP_PROFILE", "small")}

    @task(task_id="extract_industrial_data")
    def extract_industrial_data(_: dict[str, object]) -> None:
        _run("python", "-m", "industrial_intelligence.cli", "generate", "--profile", os.getenv("IIP_PROFILE", "small"))
        _run("python", "-m", "industrial_intelligence.cli", "load-sources")

    @task(task_id="validate_and_normalize")
    def validate_and_normalize() -> dict[str, object]:
        _run(
            "python",
            "-m",
            "industrial_intelligence.cli",
            "validate",
            "--source",
            "mongodb-export",
        )
        return json.loads((DATA_DIR / "processed" / "quality_report.json").read_text())

    @task(task_id="export_mongodb_snapshot")
    def export_mongodb_snapshot() -> dict[str, object]:
        from industrial_intelligence.database.mongodb import export_sensor_documents

        return export_sensor_documents(
            DATA_DIR,
            batch_size=int(os.getenv("IIP_MONGO_EXPORT_BATCH_SIZE", "5000")),
        )

    @task(task_id="enforce_source_quality_gate")
    def enforce_source_quality_gate() -> dict[str, object]:
        from industrial_intelligence.quality_gate import QualityGateError, validate_source_gate

        try:
            return validate_source_gate(DATA_DIR)
        except QualityGateError as exc:
            raise AirflowException(str(exc)) from exc

    spark_transform = BashOperator(
        task_id="run_spark_transformation",
        bash_command=(
            "spark-submit --master spark://spark-master:7077 "
            "/opt/iip/src/industrial_intelligence/spark_jobs/transform.py --data-dir /opt/iip/data"
        ),
        execution_timeout=timedelta(hours=2),
    )
    feature_gate = BashOperator(
        task_id="enforce_feature_quality_gate",
        bash_command=(
            "spark-submit --master spark://spark-master:7077 "
            "/opt/iip/src/industrial_intelligence/spark_jobs/feature_gate.py --data-dir /opt/iip/data"
        ),
        execution_timeout=timedelta(hours=1),
    )
    calculate_metrics = BashOperator(
        task_id="calculate_machine_metrics",
        bash_command="python -m industrial_intelligence.cli metrics",
    )
    mllib_inference = BashOperator(
        task_id="run_mllib_training_and_inference",
        bash_command="spark-submit --master spark://spark-master:7077 /opt/iip/src/industrial_intelligence/ml/train.py --data-dir /opt/iip/data",
        execution_timeout=timedelta(hours=2),
    )

    @task(task_id="persist_postgresql_results")
    def persist_postgresql_results() -> dict[str, int]:
        from industrial_intelligence.database.postgres import load_machine_metrics, load_ml_predictions

        metric_rows = load_machine_metrics(DATA_DIR / "processed" / "machine_metrics.csv")
        prediction_rows = load_ml_predictions(DATA_DIR / "processed" / "ml_predictions_json")
        return {"metrics": metric_rows, "predictions": prediction_rows}

    @task(task_id="synchronize_neo4j_relationships")
    def synchronize_neo4j_relationships() -> int:
        from industrial_intelligence.database.neo4j import sync_components

        return sync_components(DATA_DIR / "raw" / "neo4j" / "machine_components.csv")

    @task(task_id="run_final_consistency_checks")
    def run_final_consistency_checks(
        quality: dict[str, object],
        postgres_rows: dict[str, int],
        graph_rows: int,
    ) -> dict[str, object]:
        from industrial_intelligence.database.postgres import read_connection

        feature_quality = json.loads(
            (DATA_DIR / "processed" / "feature_quality_report.json").read_text()
        )
        with read_connection() as connection:
            prediction_total = int(
                connection.execute("SELECT count(*) AS count FROM ml_predictions").fetchone()["count"]
            )
            model_versions = {
                row["model_version"]: int(row["count"])
                for row in connection.execute(
                    """
                    SELECT model_version, count(*) AS count
                    FROM ml_predictions GROUP BY model_version ORDER BY model_version
                    """
                ).fetchall()
            }
            metric_total = int(
                connection.execute("SELECT count(*) AS count FROM machine_daily_metrics").fetchone()["count"]
            )
        if postgres_rows["metrics"] != 50 or metric_total < 50:
            raise AirflowException("Final consistency failed: incomplete machine metrics")
        if postgres_rows["predictions"] <= 0 or prediction_total < postgres_rows["predictions"]:
            raise AirflowException("Final consistency failed: incomplete ML predictions")
        if graph_rows != 200:
            raise AirflowException("Final consistency failed: incomplete Neo4j component synchronization")
        return {
            "status": "passed",
            "source_quality": quality,
            "feature_quality": feature_quality,
            "postgres_loaded": postgres_rows,
            "postgres_prediction_total": prediction_total,
            "postgres_model_versions": model_versions,
            "postgres_metric_total": metric_total,
            "neo4j_source_rows": graph_rows,
        }

    @task(task_id="generate_pipeline_summary")
    def generate_pipeline_summary(consistency: dict[str, object]) -> None:
        from airflow.operators.python import get_current_context
        from industrial_intelligence.database.postgres import record_pipeline_run

        context = get_current_context()
        summary = {**consistency, "status": "success"}
        Path("/opt/iip/reports/airflow_latest.json").write_text(json.dumps(summary, indent=2))
        record_pipeline_run(
            run_id=str(context["run_id"]),
            profile=os.getenv("IIP_PROFILE", "small"),
            quality=consistency["source_quality"],
            summary=summary,
        )

    source_metadata = validate_sources()
    extracted = extract_industrial_data(source_metadata)
    exported = export_mongodb_snapshot()
    quality = validate_and_normalize()
    extracted >> exported >> quality
    source_gate = enforce_source_quality_gate()
    quality >> source_gate >> spark_transform >> feature_gate
    feature_gate >> [calculate_metrics, mllib_inference]
    postgres_rows = persist_postgresql_results()
    graph_rows = synchronize_neo4j_relationships()
    [calculate_metrics, mllib_inference] >> postgres_rows
    source_gate >> graph_rows
    consistency = run_final_consistency_checks(source_gate, postgres_rows, graph_rows)
    generate_pipeline_summary(consistency)


industrial_etl()
