# Teststrategie

Unit-Tests prüfen Konfiguration, deterministische IDs, 50 konsistente Maschinen, bytegleiche Generierung, Dokumentnormalisierung, Quarantäne und die lokale Aggregation. Der E2E-Smoke-Test läuft vom Generator bis zur gespeicherten Prognose. Integrationstests prüfen PostgreSQL, MongoDB und Neo4j erst nach explizitem `RUN_CONTAINER_TESTS=1`.

```bash
make test
PYTHONPATH=src .venv/bin/pytest tests/unit
RUN_CONTAINER_TESTS=1 EXPECTED_PROFILE=full PYTHONPATH=src .venv/bin/pytest -m integration
docker compose exec airflow-scheduler airflow dags test industrial_etl 2026-10-19
```

Spark- und Full-Profil-Läufe sind getrennt, damit schnelle Änderungen nicht durch lange Tests blockiert werden. Ausführungsnachweise stehen im Abschlussbericht; der Text unterscheidet bestanden, übersprungen und nicht ausgeführt.

## Ausgeführter Abnahmestand vom 19. Oktober 2026

- 17 schnelle Unit-/E2E-Tests bestanden, 5 markierte Tests in diesem Lauf abgewählt.
- 4 Containerintegrationstests gegen PostgreSQL, MongoDB und Neo4j mit `EXPECTED_PROFILE=full` bestanden.
- Airflow-DAG-Import ohne Fehler; `industrial_etl` mit allen zehn Tasks gelistet.
- Vollständiger Airflow-DAG mit einer Million Messungen erfolgreich.
- MLlib-Airflow-Task nach Pfadkorrektur erneut erfolgreich; Report und Modelle im gemeinsamen Volume gespeichert.
