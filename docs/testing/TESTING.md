# Teststrategie

Die Testpyramide trennt schnelle Vertrags- und API-Tests, Spark-Semantik und reale Dienstintegration. Unit-Tests prüfen unter anderem deterministische Generierung, zentrale Validierungsregeln, MongoDB-Snapshot-Sicherheit, beide Quality Gates, Pagination, Modellversionierung, Fehlerabbildung und Neo4j-Antworten. Integrationstests lesen die tatsächlich laufenden Datenbanken.

```bash
make test
PYTHONPATH=src .venv/bin/pytest tests/unit

RUN_CONTAINER_TESTS=1 EXPECTED_PROFILE=full \
POSTGRES_DSN='postgresql://industrial:<passwort>@127.0.0.1:5432/industrial' \
MONGO_URI='mongodb://industrial:<passwort>@127.0.0.1:27017/industrial?authSource=admin' \
NEO4J_URI='bolt://127.0.0.1:7687' NEO4J_USER=neo4j NEO4J_PASSWORD='<passwort>' \
PYTHONPATH=src .venv/bin/pytest -m integration

docker compose exec airflow-scheduler airflow dags list-import-errors
```

`tests/spark/test_validation_contract.py` prüft, dass Python- und Spark-Pfad dieselben Werte an den Bereichsgrenzen akzeptieren. Der Test benötigt die optionale PySpark-Abhängigkeit. Fehlt sie auf dem Host, wird er explizit übersprungen; der produktive Spark-Pfad bleibt durch den vollständigen DAG-Lauf abgedeckt.

## Ausgeführter Abnahmestand vom 19. Oktober 2026

- 32 Tests bestanden: schnelle Tests plus vier reale Containerintegrationstests gegen PostgreSQL, MongoDB und Neo4j.
- 1 Spark-Vertragstest auf dem Host übersprungen, weil PySpark dort nicht installiert war.
- Compose-Konfiguration valide; Airflow-DAG-Import ohne Fehler.
- `industrial_etl` mit 13 Tasks gelistet.
- vollständiger Lauf `hardening_full_20261019T1028Z` mit 1.000.000 Messungen und allen 13 Tasks erfolgreich.
- MongoDB: 1.000.000 Dokumente; PostgreSQL: 50 Metriken und 1.950 Prognosen; Neo4j: 220 Komponenten und 400 Beziehungen.
- reale FastAPI-Aufrufe gegen PostgreSQL und Neo4j erfolgreich, einschließlich Pagination- und Modellversions-Headern.

Der Teststand belegt die lokale technische Integration. Er belegt weder Produktionsreife noch reale Modellgüte.
