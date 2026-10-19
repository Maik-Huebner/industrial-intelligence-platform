# Betriebsanleitung

## Voraussetzungen

- Linux oder Docker Desktop
- Docker Engine 27+ und Compose v2
- empfohlen 8 CPU-Threads, 12 GB RAM für den Stack, 15 GB freier Speicher
- Ports 5432, 7474, 7687, 8000, 8080 bis 8082 und 27017 frei

## Start

1. `.env.example` nach `.env` kopieren.
2. alle Beispielpasswörter und Airflow-Schlüssel ersetzen.
3. `docker compose config --quiet` ausführen.
4. `docker compose up -d --build` starten.
5. `docker compose ps` und die Healthchecks prüfen.
6. DAG manuell triggern oder Jobs einzeln ausführen.

## Diagnose

```bash
docker compose ps
docker compose logs --tail=200 airflow-scheduler
docker compose logs --tail=200 spark-worker
docker compose exec airflow-scheduler airflow dags list-import-errors
curl -fsS http://localhost:8000/health
```

## Neustart und Daten

`docker compose down` erhält benannte Datenvolumes. `docker compose down -v` löscht sie und darf nur nach bewusster Freigabe verwendet werden. Dateibasierte Arbeitsdaten liegen unter `data/` und werden nicht automatisch gelöscht.

## Fehlerbilder

- Airflow wartet auf PostgreSQL: Healthcheck und Passwortübereinstimmung prüfen.
- Spark-Task erreicht Master nicht: `spark-master:7077` aus dem Airflow-Netz testen.
- ML-Training hat nur eine Klasse: Generatorprofil, Fehlerquote und Featurefenster prüfen; keine Metrik erfinden.
- Qualitätsgate schlägt fehl: Reason Codes in der Quarantäne aggregieren und Quelle korrigieren.

