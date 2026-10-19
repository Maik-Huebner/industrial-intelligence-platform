"""MongoDB ingestion, snapshot export, and aggregation helpers."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class MongoSnapshotError(RuntimeError):
    """Raised when a MongoDB snapshot cannot be loaded or exported safely."""


def _client() -> Any:
    from pymongo import MongoClient

    return MongoClient(
        os.getenv(
            "MONGO_URI",
            "mongodb://industrial:change-me@mongodb:27017/industrial?authSource=admin",
        ),
        serverSelectionTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000")),
        connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000")),
    )


def load_sensor_documents(path: Path, batch_size: int = 5_000) -> int:
    """Atomically replace the active collection from a streamed JSONL snapshot.

    A temporary collection protects the last complete source snapshot if parsing,
    uniqueness validation, MongoDB, or the network fails midway through loading.
    """
    client = _client()
    database = client[os.getenv("MONGO_DATABASE", "industrial")]
    temporary_name = f"sensor_readings_staging_{uuid.uuid4().hex}"
    staging = database[temporary_name]
    loaded = 0
    digest = hashlib.sha256()
    started_at = datetime.now(UTC)
    try:
        client.admin.command("ping")
        staging.create_index("reading_id", unique=True)
        staging.create_index([("machine_id", 1), ("timestamp", -1)])
        staging.create_index([("context.scenario", 1), ("machine_id", 1)])
        batch: list[dict[str, object]] = []
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                digest.update(raw_line)
                try:
                    document = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise MongoSnapshotError(f"Invalid JSON at source line {line_number}") from exc
                batch.append(document)
                if len(batch) >= batch_size:
                    staging.insert_many(batch, ordered=True)
                    loaded += len(batch)
                    batch.clear()
            if batch:
                staging.insert_many(batch, ordered=True)
                loaded += len(batch)
        if staging.count_documents({}) != loaded:
            raise MongoSnapshotError("MongoDB staging count does not match the loaded snapshot")
        staging.rename("sensor_readings", dropTarget=True)
        database["pipeline_documents"].replace_one(
            {"_id": "active_sensor_snapshot"},
            {
                "_id": "active_sensor_snapshot",
                "collection": "sensor_readings",
                "records": loaded,
                "source_sha256": digest.hexdigest(),
                "batch_size": batch_size,
                "started_at": started_at,
                "completed_at": datetime.now(UTC),
            },
            upsert=True,
        )
        return loaded
    except MongoSnapshotError:
        staging.drop()
        raise
    except Exception as exc:
        staging.drop()
        raise MongoSnapshotError("MongoDB sensor snapshot load failed") from exc
    finally:
        client.close()


def export_sensor_documents(data_dir: Path, batch_size: int = 5_000) -> dict[str, object]:
    """Stream the active MongoDB collection into a deterministic Spark snapshot."""
    output_dir = data_dir / "processed" / "mongodb_export"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sensor_readings.jsonl"
    temporary_path = output_dir / "sensor_readings.jsonl.tmp"
    manifest_path = output_dir / "manifest.json"
    client = _client()
    collection = client[os.getenv("MONGO_DATABASE", "industrial")]["sensor_readings"]
    started_at = datetime.now(UTC)
    digest = hashlib.sha256()
    exported = 0
    duplicates = 0
    missing_ids = 0
    first_reading_id: str | None = None
    last_reading_id: str | None = None
    try:
        client.admin.command("ping")
        source_count = collection.count_documents({})
        cursor = collection.find({}, {"_id": 0}).sort("reading_id", 1).batch_size(batch_size)
        with temporary_path.open("wb") as handle:
            for document in cursor:
                reading_id = document.get("reading_id")
                if reading_id in (None, ""):
                    missing_ids += 1
                else:
                    current_id = str(reading_id)
                    if current_id == last_reading_id:
                        duplicates += 1
                    if first_reading_id is None:
                        first_reading_id = current_id
                    last_reading_id = current_id
                line = (json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n").encode()
                handle.write(line)
                digest.update(line)
                exported += 1
        if exported != source_count:
            raise MongoSnapshotError(
                f"MongoDB export count mismatch: source={source_count}, exported={exported}"
            )
        if duplicates or missing_ids:
            raise MongoSnapshotError(
                f"MongoDB export identity check failed: duplicates={duplicates}, missing={missing_ids}"
            )
        temporary_path.replace(output_path)
        manifest: dict[str, object] = {
            "source": "mongodb",
            "database": os.getenv("MONGO_DATABASE", "industrial"),
            "collection": "sensor_readings",
            "source_count": source_count,
            "exported_count": exported,
            "duplicate_reading_ids": duplicates,
            "missing_reading_ids": missing_ids,
            "sort": ["reading_id", 1],
            "batch_size": batch_size,
            "sha256": digest.hexdigest(),
            "first_reading_id": first_reading_id,
            "last_reading_id": last_reading_id,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "output": str(output_path),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest
    except MongoSnapshotError:
        temporary_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise MongoSnapshotError("MongoDB sensor export failed") from exc
    finally:
        client.close()


def anomaly_summary() -> list[dict[str, object]]:
    client = _client()
    try:
        return list(
            client[os.getenv("MONGO_DATABASE", "industrial")]["sensor_readings"].aggregate(
                [
                    {"$match": {"context.scenario": {"$ne": "normal_operation"}}},
                    {
                        "$group": {
                            "_id": "$machine_id",
                            "events": {"$sum": 1},
                            "avg_temp": {"$avg": "$sensors.temperature.value"},
                        }
                    },
                    {"$project": {"_id": 0, "machine_id": "$_id", "events": 1, "avg_temp": 1}},
                    {"$sort": {"events": -1}},
                ]
            )
        )
    finally:
        client.close()
