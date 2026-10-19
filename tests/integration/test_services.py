import os

import pytest


@pytest.mark.integration
def test_postgresql_connection() -> None:
    if not os.getenv("RUN_CONTAINER_TESTS"):
        pytest.skip("set RUN_CONTAINER_TESTS=1 inside the service network")
    import psycopg

    with psycopg.connect(os.environ["POSTGRES_DSN"]) as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.integration
def test_mongodb_connection() -> None:
    if not os.getenv("RUN_CONTAINER_TESTS"):
        pytest.skip("set RUN_CONTAINER_TESTS=1 inside the service network")
    from pymongo import MongoClient

    assert MongoClient(os.environ["MONGO_URI"]).admin.command("ping")["ok"] == 1


@pytest.mark.integration
def test_neo4j_connection() -> None:
    if not os.getenv("RUN_CONTAINER_TESTS"):
        pytest.skip("set RUN_CONTAINER_TESTS=1 inside the service network")
    from neo4j import GraphDatabase

    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])) as driver:
        assert driver.execute_query("RETURN 1 AS value").records[0]["value"] == 1


@pytest.mark.integration
def test_loaded_full_profile_is_consistent() -> None:
    if os.getenv("EXPECTED_PROFILE") != "full":
        pytest.skip("set EXPECTED_PROFILE=full after loading the full generated profile")
    import psycopg
    from neo4j import GraphDatabase
    from pymongo import MongoClient

    with psycopg.connect(os.environ["POSTGRES_DSN"]) as connection:
        assert connection.execute("SELECT count(*) FROM machines").fetchone()[0] == 50
        assert connection.execute("SELECT count(*) FROM production_orders").fetchone()[0] == 600
        assert connection.execute("SELECT count(*) FROM machine_daily_metrics").fetchone()[0] == 50
        current_predictions = connection.execute(
            "SELECT count(*) FROM ml_predictions WHERE model_version = %s",
            ("synthetic-v2-classification-benchmark",),
        ).fetchone()[0]
        assert current_predictions == 950
    assert MongoClient(os.environ["MONGO_URI"])["industrial"]["sensor_readings"].count_documents({}) == 1_000_000
    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])) as driver:
        records, _, _ = driver.execute_query("MATCH (c:Component) RETURN count(c) AS count")
        assert records[0]["count"] == 220
