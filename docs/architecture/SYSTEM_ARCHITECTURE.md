# Systemarchitektur

## Architektur in einem Satz

Die Plattform ist eine lokal containerisierte Batch-Architektur: Airflow orchestriert einen nachweisbaren MongoDB-Sensorpfad, Spark und MLlib verarbeiten freigegebene Features, PostgreSQL veröffentlicht relationale Ergebnisse, Neo4j beantwortet Abhängigkeitsfragen und FastAPI stellt beide Datenbanken typisiert bereit.

## Komponenten

| Komponente | Verantwortung | Verifizierter Zustand |
|---|---|---|
| Python-Generator und CLI | deterministische Quellen, lokale Referenzpipeline, DB-Adapter | Profile mit 10.000, 100.000 und 1.000.000 Zeilen unterstützt |
| MongoDB 7.0.14 | aktive verschachtelte Sensorquelle und Snapshot-Metadaten | 1.000.000 Dokumente, eindeutige IDs |
| Python-Qualität | Rohdatenvertrag, normalisierte CSV, Quarantäne | 994.905 gültig, 5.095 tolerierte Defekte |
| Spark 3.5.3 | Filterung, Joins, SQL, Windows, Aggregation, Parquet | 4.950 Featurezeilen für 50 Maschinen |
| Spark MLlib | fünf Klassifikatoren, Regression und KMeans | purged Splits, gemessene Benchmarks, überschreibbare Modellartefakte |
| PostgreSQL 16.4 | Stammdaten, Events, Tagesmetriken, Modellversionen, Läufe | direkte Serving-Quelle der FastAPI |
| Neo4j 5.23 | Maschinen, Komponenten und geteilte Utilities | direkte Serving-Quelle für Abhängigkeiten |
| Airflow 2.10.2 | 13 Tasks, Retries, Timeouts, zwei frühe Gates, finale Konsistenz | DAG importierbar, Reihenfolge verifiziert |
| FastAPI | typisierte, paginierte Read API | PostgreSQL- und Neo4j-Pfade live geprüft |
| Docker Compose | lokales Netzwerk, Healthchecks und Volumes | veröffentlichte Ports standardmäßig nur lokal |

## Container und Persistenz

Compose definiert zehn Services. PostgreSQL, MongoDB, Neo4j und Airflow-Logs verwenden benannte Volumes. Daten, Reports und Modelle liegen auf gemeinsamen Host-Mounts. Spark-Driver und Worker sehen `data` unter demselben absoluten Pfad `/opt/iip/data`.

Der Sensorpfad besitzt eine klare Veröffentlichungsgrenze. Der Loader befüllt zuerst eine temporäre MongoDB-Collection, prüft ihre Zeilenzahl und ersetzt die aktive Collection atomar. Der Export schreibt zunächst eine temporäre Datei und veröffentlicht sie erst nach Zählungs- und ID-Prüfung. Ein fehlgeschlagener Teilschritt ersetzt damit weder die letzte vollständige MongoDB-Quelle noch den letzten vollständigen Spark-Snapshot.

## Schnittstellen

| Von | Nach | Schnittstelle | Daten |
|---|---|---|---|
| Generator | PostgreSQL | psycopg | Maschinen, Aufträge, Wartung, Störungen |
| Generator | MongoDB | PyMongo-Batches | verschachtelte Sensordokumente |
| MongoDB | Spark-Staging | sortierter PyMongo-Cursor | JSONL plus Manifest und SHA-256 |
| Airflow | Spark | Standalone-Protokoll auf Port 7077 | Transformations-, Gate- und ML-Jobs |
| Spark | gemeinsames Volume | Parquet, JSON, Modellverzeichnisse | Features und Ergebnisse |
| Airflow | PostgreSQL/Neo4j | psycopg/Bolt | veröffentlichte Ergebnisse und Graph |
| FastAPI | PostgreSQL | parameterisierte SQL-Abfragen | Maschinen, Metriken, Prognosen, Läufe |
| FastAPI | Neo4j | parametrisierte Cypher-Abfrage | Komponentenabhängigkeiten |

## Vertrauens- und Betriebsgrenzen

- Die API ist unauthentifiziert und für lokale Demonstration vorgesehen. `IIP_BIND_ADDRESS` steht standardmäßig auf `127.0.0.1`.
- Query-Parameter besitzen Muster-, Bereichs- und Mengenlimits. Datenbankfehler führen zu generischen 503-Antworten ohne Verbindungsdaten.
- Beispielpasswörter dienen nur dem lokalen Setup. Ein externer Betrieb benötigt Secret-Management, TLS, Autorisierung, Rate Limits, Backups und zentralisierte Observability.
- Airflow-XCom enthält nur kompakte Metadaten. Massendaten bleiben in Datenbanken und Dateien.
