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
        _run("python", "-m", "industrial_intelligence.cli", "validate")
        return json.loads((DATA_DIR / "processed" / "quality_report.json").read_text())

    spark_transform = BashOperator(
        task_id="run_spark_transformation",
        bash_command=(
            "spark-submit --master spark://spark-master:7077 "
            "/opt/iip/src/industrial_intelligence/spark_jobs/transform.py --data-dir /opt/iip/data"
        ),
        execution_timeout=timedelta(hours=2),
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
    def persist_postgresql_results() -> int:
        from industrial_intelligence.database.postgres import load_machine_metrics, load_ml_predictions

        metric_rows = load_machine_metrics(DATA_DIR / "processed" / "machine_metrics.csv")
        prediction_rows = load_ml_predictions(DATA_DIR / "processed" / "ml_predictions_json")
        return metric_rows + prediction_rows

    @task(task_id="synchronize_neo4j_relationships")
    def synchronize_neo4j_relationships() -> int:
        from industrial_intelligence.database.neo4j import sync_components

        return sync_components(DATA_DIR / "raw" / "neo4j" / "machine_components.csv")

    @task(task_id="run_data_quality_checks")
    def run_data_quality_checks(report: dict[str, object]) -> dict[str, object]:
        valid = int(report["valid"])
        rejected = int(report["rejected"])
        if valid == 0 or rejected / (valid + rejected) > 0.02:
            raise AirflowException(f"Data quality gate failed: {report}")
        return {"valid": valid, "rejected": rejected, "gate": "passed"}

    @task(task_id="generate_pipeline_summary")
    def generate_pipeline_summary(quality: dict[str, object], postgres_rows: int, graph_rows: int) -> None:
        summary = {"status": "success", "quality": quality, "postgres_rows": postgres_rows, "neo4j_rows": graph_rows}
        Path("/opt/iip/reports/airflow_latest.json").write_text(json.dumps(summary, indent=2))

    source_metadata = validate_sources()
    extracted = extract_industrial_data(source_metadata)
    quality = validate_and_normalize()
    extracted >> quality >> spark_transform >> calculate_metrics >> mllib_inference
    postgres_rows = persist_postgresql_results()
    graph_rows = synchronize_neo4j_relationships()
    mllib_inference >> [postgres_rows, graph_rows]
    gate = run_data_quality_checks(quality)
    [postgres_rows, graph_rows] >> gate
    generate_pipeline_summary(gate, postgres_rows, graph_rows)


industrial_etl()
