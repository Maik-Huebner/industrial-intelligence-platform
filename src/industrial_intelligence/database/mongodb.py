"""MongoDB batch loader and aggregation examples."""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_sensor_documents(path: Path, batch_size: int = 5_000) -> int:
    from pymongo import MongoClient, ReplaceOne

    client = MongoClient(os.getenv("MONGO_URI", "mongodb://industrial:change-me@mongodb:27017/industrial?authSource=admin"))
    collection = client[os.getenv("MONGO_DATABASE", "industrial")]["sensor_readings"]
    operations: list[ReplaceOne] = []
    loaded = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            document = json.loads(line)
            operations.append(ReplaceOne({"reading_id": document["reading_id"]}, document, upsert=True))
            if len(operations) >= batch_size:
                collection.bulk_write(operations, ordered=False)
                loaded += len(operations)
                operations.clear()
        if operations:
            collection.bulk_write(operations, ordered=False)
            loaded += len(operations)
    return loaded


def anomaly_summary() -> list[dict[str, object]]:
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URI"])
    return list(
        client[os.getenv("MONGO_DATABASE", "industrial")]["sensor_readings"].aggregate(
            [
                {"$match": {"context.scenario": {"$ne": "normal_operation"}}},
                {"$group": {"_id": "$machine_id", "events": {"$sum": 1}, "avg_temp": {"$avg": "$sensors.temperature.value"}}},
                {"$project": {"_id": 0, "machine_id": "$_id", "events": 1, "avg_temp": 1}},
                {"$sort": {"events": -1}},
            ]
        )
    )

