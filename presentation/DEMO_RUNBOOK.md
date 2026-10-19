# Demo-Runbook

Ziel: eine reproduzierbare 90-Sekunden-Demo ohne Full-Training während des Vortrags. Der Full-Lauf wird durch persistierte, geprüfte Evidenz gezeigt.

## Vorbereitung am Vortag

```bash
cp .env.example .env
# Alle Beispielpasswörter in .env ersetzen.
docker compose config --quiet
docker compose --profile pipeline up -d --build
docker compose --profile pipeline ps
```

Bei belegten Hostports ausschließlich `*_HOST_PORT` in `.env` anpassen; interne Containerports nicht ändern. Die folgende Kurzform übernimmt den konfigurierten API-Port:

```bash
set -a; source .env; set +a
export DEMO_API="http://127.0.0.1:${APP_HOST_PORT:-8000}"
export DEMO_AIRFLOW="http://127.0.0.1:${AIRFLOW_HOST_PORT:-8080}"
```

Vor der Präsentation einmal prüfen:

```bash
curl -fsS "$DEMO_API/health"
curl -fsS "$DEMO_API/pipeline-runs/latest" | python -m json.tool
curl -fsS "$DEMO_API/machines/M-001/dependencies" | python -m json.tool
```

Erwartung: Health `status: ok`, PostgreSQL verfügbar, ein erfolgreicher Pipeline-Lauf und eine nicht leere Neo4j-Antwort. Browser-Tabs für Präsentation, Airflow und optional API-Docs vorab öffnen. Keine Passwörter oder `.env` zeigen.

## Live-Demo: 90 Sekunden

### 1. Laufende Plattform · 0–20 s

```bash
docker compose --profile pipeline ps
```

Zeigen: PostgreSQL, MongoDB, Neo4j, Spark Master, API und Airflow Webserver sind gesund; Scheduler und Spark Worker laufen. Darauf hinweisen, dass alle Hostports an `127.0.0.1` gebunden sind.

### 2. API und Laufstatus · 20–45 s

```bash
curl -fsS "$DEMO_API/health" | python -m json.tool
curl -fsS "$DEMO_API/pipeline-runs/latest" | python -m json.tool
```

Zeigen: API liest den realen PostgreSQL-Status; Authentifizierung ist bewusst nur für die lokale Demo nicht konfiguriert. Der letzte Lauf enthält Status, Profil, Zeitstempel und Run-ID.

### 3. Versionierte ML-Ergebnisse · 45–65 s

```bash
curl -i -fsS \
  "$DEMO_API/predictions?model_version=synthetic-v2-classification-benchmark&limit=2"
```

Zeigen: Pagination-/Versionsheader und zwei persistierte Prognosen. Nicht behaupten, der Wert sei eine reale Ausfallwahrscheinlichkeit; es ist ein synthetischer Modellscore.

### 4. Graphabhängigkeit · 65–90 s

```bash
curl -fsS "$DEMO_API/machines/M-001/dependencies" | python -m json.tool
```

Zeigen: Die Antwort stammt direkt aus Neo4j und enthält Komponenten/technische Abhängigkeiten. Abschluss: PostgreSQL dient strukturierte Ergebnisse, Neo4j den Kontext, MongoDB bleibt Spark-Sensorquelle.

## Airflow-Nachweis, falls 30 Sekunden zusätzlich verfügbar sind

Im Browser `$DEMO_AIRFLOW` öffnen, DAG `industrial_etl` auswählen und den letzten grünen Lauf zeigen. Erwartung: **13 Tasks**, nicht zehn. Keinen Full-Lauf während der Präsentation starten.

## Fallback ohne laufende Container

In dieser Reihenfolge öffnen:

1. `reports/airflow_latest.json`: Full-Quellqualität, 4.950 Features, Split und Persistenz.
2. `reports/classification_benchmark.json`: fünf Modelle und finale Confusion Matrix.
3. `reports/ml_report.json`: finale Klassifikation, purged Regression und KMeans.
4. `docs/audit/FINAL_QUALITY_AUDIT.md`: Fresh-Start-, Test- und Release-Nachweis.

Gesicherte Kernaussagen:

```text
Full:   1.000.000 Sensoren -> 994.905 valide + 5.095 Quarantäne
Spark:  4.950 Tagesfeatures
ML:     Macro-F1 0,534 | Balanced Accuracy 0,537 | TN/FP/FN/TP 41/187/76/646
DB:     1.950 versionierte Prognosen | 50 Maschinen | 220 Komponenten | 400 Beziehungen
Airflow: 13/13 Tasks erfolgreich
Tests:  32 bestanden; Spark-Verträge zusätzlich im Container bestanden
```

## Fehlerbehandlung

- **Port belegt:** Host-Port in `.env` ändern und `docker compose up -d` erneut ausführen.
- **Dienst startet noch:** Healthcheck abwarten; keine hektische Neuinitialisierung. Fallback zeigen.
- **Airflow-UI langsam:** `reports/airflow_latest.json` verwenden.
- **API 503:** `docker compose logs --tail=100 app postgres neo4j` prüfen; Fallback verwenden.
- **Spark-Ressourcen knapp:** Keinen parallelen zweiten Stack und keinen Full-Lauf starten.
- **Leere Prognosen:** explizite Version wie oben verwenden und `reports/classification_benchmark.json` zeigen.

## Nach der Demo

```bash
docker compose --profile pipeline stop
```

`stop` erhält die Volumes. `down -v` ist für eine normale Demo ausdrücklich nicht vorgesehen.
