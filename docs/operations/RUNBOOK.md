# Betriebsanleitung

## Voraussetzungen

- Linux oder Docker Desktop mit Compose v2
- empfohlen: 8 CPU-Threads, 12 GB RAM und 15 GB freier Speicher für das Full-Profil
- lokale Ports 5432, 7474, 7687, 8000, 8080 bis 8082 und 27017 frei oder in `.env` umkonfigurieren

## Sicherer lokaler Start

1. `.env.example` nach `.env` kopieren.
2. Beispielpasswörter und Airflow-Schlüssel ersetzen.
3. `IIP_BIND_ADDRESS=127.0.0.1` beibehalten.
4. `docker compose config --quiet` ausführen.
5. `docker compose --profile pipeline up -d --build` starten.
6. Healthchecks, DAG-Import und API prüfen.

```bash
docker compose --profile pipeline ps
docker compose exec airflow-scheduler airflow dags list-import-errors
curl -fsS http://127.0.0.1:8000/health
```

Die API hat absichtlich noch keine Authentifizierung. `IIP_BIND_ADDRESS` darf deshalb nicht ohne vorgeschaltete Authentifizierung, Autorisierung, TLS, Rate Limits und Netzwerkregeln auf `0.0.0.0` gesetzt werden.

## Vollständigen DAG ausführen

```bash
docker compose exec airflow-scheduler \
  airflow dags trigger industrial_etl --run-id <eindeutige-run-id>
docker compose exec airflow-scheduler \
  airflow dags list-runs -d industrial_etl --no-backfill
```

Ein erfolgreicher Lauf weist 13 erfolgreiche Tasks aus. `pipeline_runs` erhält erst nach dem finalen Konsistenzcheck eine erfolgreiche Zeile.

## Diagnose

```bash
docker compose logs --tail=200 airflow-scheduler
docker compose logs --tail=200 spark-worker
docker compose exec airflow-scheduler airflow tasks states-for-dag-run industrial_etl <run-id>
curl -fsS 'http://127.0.0.1:8000/pipeline-runs?limit=5'
```

Typische Fehlerbilder:

- `export_mongodb_snapshot` schlägt fehl: MongoDB-Erreichbarkeit, aktiven Snapshot und Dokumentzahl prüfen; die temporäre Exportdatei wird nicht veröffentlicht.
- `enforce_source_quality_gate` schlägt fehl: Generator-, Export- und Qualitätsmanifest vergleichen; Quarantänegründe aggregieren.
- `enforce_feature_quality_gate` schlägt fehl: Nullschlüssel, Maschinenabdeckung, Klassenverteilung und Split-Grenzen prüfen.
- API antwortet `503`: PostgreSQL beziehungsweise Neo4j prüfen; interne Verbindungsdetails werden nicht nach außen gegeben.
- ML-Training sieht nur eine Klasse: Quelle oder Featurebildung korrigieren; Testdaten und Metriken nicht nachträglich anpassen.

## Neustart, Wiederholung und Recovery

`docker compose down` erhält benannte Datenvolumes. `docker compose down -v` löscht sie und darf nur nach bewusster Freigabe verwendet werden. Dateiartefakte unter `data/`, `reports/` und `models/` werden nicht automatisch gelöscht.

MongoDB lädt neue Sensordaten zuerst in eine temporäre Collection. Nur ein vollständig eingelesener, gezählter Snapshot ersetzt atomar `sensor_readings`. Ein fehlgeschlagener Zwischenlauf lässt den letzten vollständigen aktiven Snapshot bestehen. PostgreSQL nutzt fachliche Upserts; historische Modellversionen bleiben erhalten.

## Bekannte Betriebsgrenzen

- keine Authentifizierung, Rollen, TLS-Terminierung oder Rate Limits in der API
- Secrets derzeit über Umgebungsvariablen, kein externer Secret Store
- keine Registry-, Drift-, SLO- oder Alarmierungsintegration
- kein automatisierter Restore-Test für Datenbankvolumes
