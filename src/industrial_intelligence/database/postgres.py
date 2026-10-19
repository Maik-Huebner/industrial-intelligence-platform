"""Idempotent PostgreSQL loading using batched upserts."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


def connection_url() -> str:
    return os.getenv(
        "POSTGRES_DSN",
        "postgresql://industrial:change-me@postgres:5432/industrial",
    )


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
