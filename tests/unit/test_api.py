from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from industrial_intelligence.api import main
from industrial_intelligence.database.postgres import PostgresUnavailable


client = TestClient(main.app)
MACHINE = {
    "machine_id": "M-017",
    "line_id": "LINE-02",
    "machine_type": "PUMP",
    "installed_year": 2020,
    "criticality": 2,
    "manufacturer": "KernTech",
}
METRIC = {
    "machine_id": "M-017",
    "metric_date": date(2026, 10, 19),
    "measurement_count": 20_000,
    "avg_temperature_c": 55.0,
    "max_temperature_c": 72.0,
    "avg_vibration_mm_s": 3.2,
    "avg_load_pct": 64.0,
    "anomaly_rate": 0.04,
    "failure_count": 3,
    "maintenance_count": 5,
    "calculated_at": datetime(2026, 10, 19, tzinfo=UTC),
}
PREDICTION = {
    "machine_id": "M-017",
    "prediction_date": date(2026, 10, 17),
    "model_name": "logistic_regression",
    "model_version": "synthetic-v2-classification-benchmark",
    "risk_probability": 0.71,
    "predicted_label": 1,
    "created_at": datetime(2026, 10, 19, tzinfo=UTC),
}


def test_health_reports_postgres_without_exposing_details(monkeypatch) -> None:
    monkeypatch.setattr(main.relational_store, "check_connection", lambda: True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "postgres_available": True,
        "authentication": "not_configured_local_only",
    }


def test_machines_are_paginated_from_postgres(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        main.relational_store,
        "fetch_machines",
        lambda limit, offset: (calls.append((limit, offset)) or [MACHINE], 50),
    )
    response = client.get("/machines?limit=1&offset=16")
    assert response.status_code == 200
    assert response.json()[0]["machine_id"] == "M-017"
    assert response.headers["x-total-count"] == "50"
    assert calls == [(1, 16)]


def test_machine_metrics_come_from_postgres(monkeypatch) -> None:
    monkeypatch.setattr(main.relational_store, "fetch_machine", lambda machine_id: MACHINE)
    monkeypatch.setattr(
        main.relational_store,
        "fetch_machine_metrics",
        lambda machine_id, limit, offset: ([METRIC], 1),
    )
    response = client.get("/machines/M-017/metrics")
    assert response.status_code == 200
    assert response.json()[0]["measurement_count"] == 20_000


def test_predictions_use_explicit_model_version_and_pagination(monkeypatch) -> None:
    captured = {}

    def fake_fetch(version, limit, offset, machine_id=None, predicted_label=None):
        captured.update(
            version=version,
            limit=limit,
            offset=offset,
            predicted_label=predicted_label,
        )
        return [PREDICTION], 950

    monkeypatch.setattr(main.relational_store, "fetch_predictions", fake_fetch)
    response = client.get(
        "/predictions?risk=high&model_version=synthetic-v2-classification-benchmark&limit=25&offset=50"
    )
    assert response.status_code == 200
    assert response.headers["x-model-version"] == "synthetic-v2-classification-benchmark"
    assert response.headers["x-total-count"] == "950"
    assert captured == {
        "version": "synthetic-v2-classification-benchmark",
        "limit": 25,
        "offset": 50,
        "predicted_label": 1,
    }


def test_unknown_and_invalid_machine_ids_are_controlled(monkeypatch) -> None:
    monkeypatch.setattr(main.relational_store, "fetch_machine", lambda machine_id: None)
    assert client.get("/machines/M-999").status_code == 404
    assert client.get("/machines/not-valid").status_code == 422


def test_postgres_failure_returns_generic_503(monkeypatch) -> None:
    def fail(limit, offset):
        raise PostgresUnavailable("secret-host.example:5432")

    monkeypatch.setattr(main.relational_store, "fetch_machines", fail)
    response = client.get("/machines")
    assert response.status_code == 503
    assert "secret-host" not in response.text


def test_neo4j_dependencies_are_bounded_and_typed(monkeypatch) -> None:
    captured = {}

    def fake_dependencies(machine_id, limit):
        captured.update(machine_id=machine_id, limit=limit)
        return {
            "machine_id": machine_id,
            "dependencies": [
                {
                    "component_id": "M-017-MOTOR",
                    "component_type": "motor",
                    "dependency_id": "UTILITY-LINE-02-motor",
                    "dependency_type": "shared_utility",
                    "affected_neighbor_machines": ["M-012"],
                    "relationship": "component DEPENDS_ON shared technical utility",
                }
            ],
        }

    monkeypatch.setattr(main.graph_store, "machine_dependencies", fake_dependencies)
    response = client.get("/machines/M-017/dependencies?limit=12")
    assert response.status_code == 200
    assert response.json()["dependencies"][0]["dependency_id"].startswith("UTILITY-")
    assert captured == {"machine_id": "M-017", "limit": 12}
