"""Idempotent PostgreSQL loading using batched upserts."""

from __future__ import annotations

import csv
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


class PostgresUnavailable(RuntimeError):
    """Raised when a read API query cannot reach or use PostgreSQL."""


def connection_url() -> str:
    return os.getenv(
        "POSTGRES_DSN",
        "postgresql://industrial:change-me@postgres:5432/industrial",
    )


@contextmanager
def read_connection() -> Iterator[Any]:
    """Open a bounded read connection without exposing driver errors upstream."""
    import psycopg
    from psycopg.rows import dict_row

    try:
        with psycopg.connect(
            connection_url(),
            connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "5")),
            options=f"-c statement_timeout={int(os.getenv('POSTGRES_STATEMENT_TIMEOUT_MS', '5000'))}",
            row_factory=dict_row,
        ) as connection:
            yield connection
    except psycopg.Error as exc:
        raise PostgresUnavailable("PostgreSQL query failed") from exc


def check_connection() -> bool:
    with read_connection() as connection:
        return connection.execute("SELECT 1 AS value").fetchone()["value"] == 1


def fetch_machines(limit: int, offset: int) -> tuple[list[dict[str, object]], int]:
    with read_connection() as connection:
        total = connection.execute("SELECT count(*) AS count FROM machines").fetchone()["count"]
        rows = connection.execute(
            """
            SELECT machine_id, line_id, machine_type, installed_year, criticality, manufacturer
            FROM machines ORDER BY machine_id LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()
    return list(rows), int(total)


def fetch_machine(machine_id: str) -> dict[str, object] | None:
    with read_connection() as connection:
        row = connection.execute(
            """
            SELECT machine_id, line_id, machine_type, installed_year, criticality, manufacturer
            FROM machines WHERE machine_id = %s
            """,
            (machine_id,),
        ).fetchone()
    return dict(row) if row else None


def fetch_machine_metrics(
    machine_id: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], int]:
    with read_connection() as connection:
        total = connection.execute(
            "SELECT count(*) AS count FROM machine_daily_metrics WHERE machine_id = %s",
            (machine_id,),
        ).fetchone()["count"]
        rows = connection.execute(
            """
            SELECT machine_id, metric_date, measurement_count, avg_temperature_c,
                   max_temperature_c, avg_vibration_mm_s, avg_load_pct, anomaly_rate,
                   failure_count, maintenance_count, calculated_at
            FROM machine_daily_metrics
            WHERE machine_id = %s
            ORDER BY metric_date DESC, calculated_at DESC
            LIMIT %s OFFSET %s
            """,
            (machine_id, limit, offset),
        ).fetchall()
    return list(rows), int(total)


def fetch_predictions(
    model_version: str,
    limit: int,
    offset: int,
    machine_id: str | None = None,
    predicted_label: int | None = None,
) -> tuple[list[dict[str, object]], int]:
    conditions = ["model_version = %s"]
    parameters: list[object] = [model_version]
    if machine_id is not None:
        conditions.append("machine_id = %s")
        parameters.append(machine_id)
    if predicted_label is not None:
        conditions.append("predicted_label = %s")
        parameters.append(predicted_label)
    where = " AND ".join(conditions)
    with read_connection() as connection:
        total = connection.execute(
            f"SELECT count(*) AS count FROM ml_predictions WHERE {where}",  # noqa: S608 - static clauses
            parameters,
        ).fetchone()["count"]
        rows = connection.execute(
            f"""
            SELECT machine_id, prediction_date, model_name, model_version,
                   risk_probability, predicted_label, created_at
            FROM ml_predictions WHERE {where}
            ORDER BY prediction_date DESC, machine_id ASC
            LIMIT %s OFFSET %s
            """,  # noqa: S608 - static clauses only
            [*parameters, limit, offset],
        ).fetchall()
    return list(rows), int(total)


def fetch_pipeline_runs(limit: int, offset: int) -> tuple[list[dict[str, object]], int]:
    with read_connection() as connection:
        total = connection.execute("SELECT count(*) AS count FROM pipeline_runs").fetchone()["count"]
        rows = connection.execute(
            """
            SELECT run_id, started_at, finished_at, status, profile,
                   input_rows, valid_rows, rejected_rows, summary
            FROM pipeline_runs
            ORDER BY started_at DESC, run_id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()
    return list(rows), int(total)


def record_pipeline_run(
    run_id: str,
    profile: str,
    quality: dict[str, object],
    summary: dict[str, object],
) -> None:
    """Persist only a completed successful run after final consistency checks."""
    import psycopg
    from psycopg.types.json import Jsonb

    now = datetime.now(UTC)
    with psycopg.connect(connection_url()) as connection:
        connection.execute(
            """
            INSERT INTO pipeline_runs(
                run_id, started_at, finished_at, status, profile,
                input_rows, valid_rows, rejected_rows, summary
            ) VALUES (%s, %s, %s, 'success', %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO UPDATE SET
                finished_at = EXCLUDED.finished_at, status = EXCLUDED.status,
                input_rows = EXCLUDED.input_rows, valid_rows = EXCLUDED.valid_rows,
                rejected_rows = EXCLUDED.rejected_rows, summary = EXCLUDED.summary
            """,
            (
                run_id,
                now,
                now,
                profile,
                quality["input_rows"],
                quality["valid_rows"],
                quality["rejected_rows"],
                Jsonb(summary),
            ),
        )
        connection.commit()


def load_machine_metrics(path: Path, batch_size: int = 1_000) -> int:
    """Upsert calculated metrics; importing psycopg remains optional locally."""
    import psycopg

    sql = """
        INSERT INTO machine_daily_metrics (
            machine_id, metric_date, measurement_count, avg_temperature_c,
            max_temperature_c, avg_vibration_mm_s, avg_load_pct,
            anomaly_rate, failure_count, maintenance_count
        ) VALUES (
            %(machine_id)s, CURRENT_DATE, %(measurement_count)s, %(avg_temperature_c)s,
            %(max_temperature_c)s, %(avg_vibration_mm_s)s, %(avg_load_pct)s,
            %(anomaly_rate)s, %(failure_count)s, %(maintenance_count)s
        )
        ON CONFLICT (machine_id, metric_date) DO UPDATE SET
            measurement_count = EXCLUDED.measurement_count,
            avg_temperature_c = EXCLUDED.avg_temperature_c,
            max_temperature_c = EXCLUDED.max_temperature_c,
            avg_vibration_mm_s = EXCLUDED.avg_vibration_mm_s,
            avg_load_pct = EXCLUDED.avg_load_pct,
            anomaly_rate = EXCLUDED.anomaly_rate,
            failure_count = EXCLUDED.failure_count,
            maintenance_count = EXCLUDED.maintenance_count,
            calculated_at = now()
    """
    loaded = 0
    with path.open(encoding="utf-8") as handle, psycopg.connect(connection_url()) as connection:
        cursor = connection.cursor()
        reader = csv.DictReader(handle)
        batch: list[dict[str, str]] = []
        for row in reader:
            batch.append(row)
            if len(batch) >= batch_size:
                cursor.executemany(sql, batch)
                loaded += len(batch)
                batch.clear()
        if batch:
            cursor.executemany(sql, batch)
            loaded += len(batch)
        connection.commit()
    return loaded


def load_source_data(data_dir: Path) -> dict[str, int]:
    """Load relational masters and file events with conflict-safe statements."""
    import psycopg
    from psycopg.types.json import Jsonb

    raw = data_dir / "raw"
    statements = {
        "machines": """
            INSERT INTO machines(machine_id,line_id,machine_type,installed_year,criticality,manufacturer)
            VALUES (%(machine_id)s,%(line_id)s,%(machine_type)s,%(installed_year)s,%(criticality)s,%(manufacturer)s)
            ON CONFLICT (machine_id) DO UPDATE SET line_id=EXCLUDED.line_id, machine_type=EXCLUDED.machine_type,
              installed_year=EXCLUDED.installed_year, criticality=EXCLUDED.criticality, manufacturer=EXCLUDED.manufacturer
        """,
        "orders": """
            INSERT INTO production_orders(order_id,line_id,product_code,planned_units,started_at,status)
            VALUES (%(order_id)s,%(line_id)s,%(product_code)s,%(planned_units)s,%(started_at)s,%(status)s)
            ON CONFLICT (order_id) DO UPDATE SET status=EXCLUDED.status, planned_units=EXCLUDED.planned_units
        """,
        "maintenance": """
            INSERT INTO maintenance_records(maintenance_id,machine_id,performed_at,maintenance_type,duration_minutes,notes)
            VALUES (%(maintenance_id)s,%(machine_id)s,%(performed_at)s,%(maintenance_type)s,%(duration_minutes)s,%(notes)s)
            ON CONFLICT (maintenance_id) DO UPDATE SET maintenance_type=EXCLUDED.maintenance_type,
              duration_minutes=EXCLUDED.duration_minutes, notes=EXCLUDED.notes
        """,
        "failures": """
            INSERT INTO normalized_machine_events(event_id,machine_id,occurred_at,event_type,severity,payload)
            VALUES (%(failure_id)s,%(machine_id)s,%(occurred_at)s,'failure',%(severity)s,%(payload)s)
            ON CONFLICT (event_id) DO UPDATE SET severity=EXCLUDED.severity, payload=EXCLUDED.payload
        """,
    }
    with (raw / "postgres/machines.csv").open(encoding="utf-8") as handle:
        machines = list(csv.DictReader(handle))
    with (raw / "postgres/production_orders.csv").open(encoding="utf-8") as handle:
        orders = list(csv.DictReader(handle))
    with (raw / "files/maintenance.csv").open(encoding="utf-8") as handle:
        maintenance = list(csv.DictReader(handle))
    failures = json.loads((raw / "files/failures.json").read_text(encoding="utf-8"))
    for row in failures:
        row["payload"] = Jsonb({"failure_type": row["failure_type"], "downtime_minutes": row["downtime_minutes"]})
    with psycopg.connect(connection_url()) as connection:
        cursor = connection.cursor()
        cursor.executemany(statements["machines"], machines)
        cursor.executemany(statements["orders"], orders)
        cursor.executemany(statements["maintenance"], maintenance)
        cursor.executemany(statements["failures"], failures)
        connection.commit()
    return {"machines": len(machines), "orders": len(orders), "maintenance": len(maintenance), "failures": len(failures)}


def load_ml_predictions(path: Path) -> int:
    """Upsert Spark-produced test predictions from its JSON output directory."""
    import psycopg

    rows: list[dict[str, object]] = []
    for part in sorted(path.glob("part-*.json")):
        with part.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle)
    sql = """
        INSERT INTO ml_predictions(machine_id,prediction_date,model_name,model_version,risk_probability,predicted_label)
        VALUES (%(machine_id)s,%(prediction_date)s,%(model_name)s,%(model_version)s,%(risk_probability)s,%(predicted_label)s)
        ON CONFLICT (machine_id,prediction_date,model_name,model_version) DO UPDATE SET
          risk_probability=EXCLUDED.risk_probability, predicted_label=EXCLUDED.predicted_label, created_at=now()
    """
    with psycopg.connect(connection_url()) as connection:
        connection.cursor().executemany(sql, rows)
        connection.commit()
    return len(rows)
