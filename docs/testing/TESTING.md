# Teststrategie

Unit-Tests prüfen Konfiguration, deterministische IDs, 50 konsistente Maschinen, bytegleiche Generierung, Dokumentnormalisierung, Quarantäne und die lokale Aggregation. Der E2E-Smoke-Test läuft vom Generator bis zur gespeicherten Prognose. Integrationstests prüfen PostgreSQL, MongoDB und Neo4j erst nach explizitem `RUN_CONTAINER_TESTS=1`.

```bash
make test
PYTHONPATH=src .venv/bin/pytest tests/unit
RUN_CONTAINER_TESTS=1 PYTHONPATH=src .venv/bin/pytest -m integration
docker compose exec airflow-scheduler airflow dags test industrial_etl 2026-10-19
```

Spark- und Full-Profil-Läufe sind getrennt, damit schnelle Änderungen nicht durch lange Tests blockiert werden. Ausführungsnachweise stehen im Abschlussbericht; der Text unterscheidet bestanden, übersprungen und nicht ausgeführt.

