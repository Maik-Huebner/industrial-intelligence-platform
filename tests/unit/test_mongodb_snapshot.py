import json

import pytest

from industrial_intelligence.database import mongodb


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction):
        self.documents = sorted(self.documents, key=lambda row: row.get(field, ""))
        return self

    def batch_size(self, size):
        return self

    def __iter__(self):
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def count_documents(self, query):
        return len(self.documents)

    def find(self, query, projection):
        return FakeCursor([{key: value for key, value in row.items() if key != "_id"} for row in self.documents])


class FakeDatabase:
    def __init__(self, documents):
        self.collection = FakeCollection(documents)

    def __getitem__(self, name):
        assert name == "sensor_readings"
        return self.collection


class FakeAdmin:
    def __init__(self, error=None):
        self.error = error

    def command(self, name):
        if self.error:
            raise self.error
        return {"ok": 1}


class FakeClient:
    def __init__(self, documents, error=None):
        self.database = FakeDatabase(documents)
        self.admin = FakeAdmin(error)
        self.closed = False

    def __getitem__(self, name):
        return self.database

    def close(self):
        self.closed = True


def document(reading_id):
    return {
        "reading_id": reading_id,
        "machine_id": "M-001",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sensors": {"temperature": {"value": 50}},
    }


def test_export_is_complete_sorted_and_reproducible(tmp_path, monkeypatch) -> None:
    documents = [document("R-003"), document("R-001"), document("R-002")]
    monkeypatch.setattr(mongodb, "_client", lambda: FakeClient(documents))
    first = mongodb.export_sensor_documents(tmp_path, batch_size=2)
    second = mongodb.export_sensor_documents(tmp_path, batch_size=2)
    assert first["source_count"] == first["exported_count"] == 3
    assert first["sha256"] == second["sha256"]
    lines = (tmp_path / "processed/mongodb_export/sensor_readings.jsonl").read_text().splitlines()
    assert [json.loads(line)["reading_id"] for line in lines] == ["R-001", "R-002", "R-003"]


def test_export_rejects_duplicate_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        mongodb,
        "_client",
        lambda: FakeClient([document("R-001"), document("R-001")]),
    )
    with pytest.raises(mongodb.MongoSnapshotError, match="identity check"):
        mongodb.export_sensor_documents(tmp_path)
    assert not (tmp_path / "processed/mongodb_export/sensor_readings.jsonl.tmp").exists()


def test_export_wraps_connection_errors(tmp_path, monkeypatch) -> None:
    client = FakeClient([], error=RuntimeError("internal server address"))
    monkeypatch.setattr(mongodb, "_client", lambda: client)
    with pytest.raises(mongodb.MongoSnapshotError, match="export failed"):
        mongodb.export_sensor_documents(tmp_path)
    assert client.closed is True
