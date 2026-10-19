# Systemarchitektur

## Architektur in einem Satz

Die Plattform ist eine lokal containerisierte Batch-Architektur: Ein deterministischer Python-Generator erzeugt quellorientierte Dateien, Airflow orchestriert die Verarbeitung, Spark und MLlib rechnen auf einem gemeinsamen Dateisystem, drei Datenbanken übernehmen getrennte Persistenzaufgaben, und FastAPI liefert derzeit dateibasierte Ergebnisse aus.

## Komponenten und Verantwortlichkeiten

| Komponente | Laufzeit | Verantwortung | Eingänge | Ausgänge | Status |
|---|---|---|---|---|---|
| CLI und Generator | Python 3.11–3.13 | deterministische synthetische Daten und lokale Referenzpipeline | Profil, Seed, Environment | CSV, JSON, JSONL, Manifest | Code und Full-Lauf verifiziert |
| Python-Qualität | Python | Normalisierung, Validierung, Quarantäne | Sensor-JSONL, Maschinen-CSV | validierte CSV, Quarantäne, Report | Code und 994.905/5.095 verifiziert |
| PostgreSQL 16.4 | Container | relationale Stamm-, Ereignis-, Kennzahlen- und Modellergebnisdaten | Source- und Ergebnis-Upserts | SQL-Abfragen, persistierte Modellversionen | laufend und abgefragt |
| MongoDB 7.0.14 | Container | vollständige verschachtelte Rohsensordokumente | JSONL-Batch-Upserts | dokumentenorientierte Rohhistorie | 1.000.000 Dokumente verifiziert |
| Neo4j 5.23 | Container | Maschinen-Komponenten-Abhängigkeiten | Komponenten-CSV | Pfad- und Abhängigkeitsgraph | 270 Knoten/400 Beziehungen verifiziert |
| Spark Master | Container | Clusterkoordination | Spark-Submit-Verbindungen | Job-Scheduling | gesund verifiziert |
| Spark Worker | Container | DataFrame- und ML-Ausführung | Tasks und gemeinsames Volume | Parquet- und Modellteile | laufend verifiziert |
| Spark-Submit/Airflow-Driver | Container | Spark-Driver und Jobstart | Python-Job, `/opt/iip/data` | Clusterjob | erfolgreicher Full-DAG verifiziert |
| Spark MLlib | Spark-Prozess | Klassifikation, Regression und Clustering | Parquet-Features | Modelle, Reports, JSON-Prognosen | gemessene Resultate verifiziert |
| Airflow 2.10.2 | Webserver, Scheduler, LocalExecutor | Batch-Orchestrierung und Status | DAG, Environment | Tasklogs, Status, Summary | zwei erfolgreiche manuelle Läufe verifiziert |
| FastAPI | App-Container | lesender REST-Zugriff auf Artefakte | Dateien auf Daten- und Report-Volume | JSON-Responses | Endpunkte live abgerufen |

## Container-Topologie

`compose.yaml` definiert zehn Services. Dauerhaft laufen PostgreSQL, MongoDB, Neo4j, Spark Master, Spark Worker, App, Airflow Webserver und Airflow Scheduler. `airflow-init` ist ein Initialisierungsjob. `spark-submit` liegt hinter dem Compose-Profil `jobs` und startet den Transformationsjob separat; innerhalb des DAG startet dagegen der Airflow-Scheduler den Spark-Driver per `spark-submit`.

### Persistenz und Mounts

- PostgreSQL, MongoDB, Neo4j und Airflow-Logs verwenden benannte Docker-Volumes.
- `./data` wird in Spark Master, Spark Worker, Spark-Submit, App und Airflow identisch nach `/opt/iip/data` gemountet.
- `./reports` und `./models` werden ebenfalls an den beteiligten Spark- und Airflow-Containern bereitgestellt.
- Der identische absolute Pfad ist für den Standalone-Cluster wesentlich: Der Driver im Airflow-Container und der Executor im Spark-Worker müssen dieselben Dateien unter demselben Pfad sehen.
- Dieser gemeinsame Mount ist der tatsächlich funktionierende Stand der früheren Driver-/Worker-Dateisystemproblematik.

## Schnittstellen

| Von | Nach | Schnittstelle | Daten |
|---|---|---|---|
| Generator | Dateistaging | lokales Dateisystem | CSV, JSON, JSONL |
| CLI | PostgreSQL | psycopg/SQL | Stammdaten, Events, Metriken, Prognosen |
| CLI | MongoDB | PyMongo | Sensordokumente |
| Airflow | Spark Master | Spark Standalone, Port 7077 | Jobdefinitionen und Tasks |
| Spark Driver/Worker | gemeinsames Volume | `/opt/iip/data` | Rohdaten, Parquet, JSON-Prognosen |
| CLI | Neo4j | Bolt/Cypher | Komponenten und Abhängigkeiten |
| FastAPI | gemeinsames Volume | Dateizugriff | Maschinen-CSV, Metrik-CSV, JSON-Prognosen, Report |
| Browser/Nutzer | FastAPI | HTTP/JSON | Health, Maschinen, Prognosen und Laufstatus |

## Zwei Ausführungspfade

### Lokaler Referenzpfad

`run_local_pipeline()` führt Generator, Python-Validierung, vollständige Historienaggregation und eine transparente Regelbewertung aus. Dieser Pfad benötigt weder Spark noch Datenbanken. Seine `risk_score`-Werte sind keine MLlib-Vorhersagen.

### Containerisierter Full-Pfad

Airflow erzeugt und lädt Quellen, validiert, startet Spark, berechnet lokale Maschinenmetriken, trainiert MLlib, persistiert PostgreSQL-Ergebnisse, synchronisiert Neo4j und schreibt die Airflow-Summary. MongoDB, PostgreSQL und Neo4j laufen als eigenständige persistente Systeme.

## Vertrauens- und Betriebsgrenzen

- Beispielpasswörter stehen in `.env.example`; reale Secrets benötigen externes Secret-Management.
- Die API ist unauthentifiziert und erwartet ein lokales Vertrauensnetz.
- TLS, rollenbasierte Autorisierung, Rate Limits, Backup-Automation und Observability-Stack sind nicht implementiert.
- Airflow ist Orchestrator. Airflow speichert keine fachlichen Massendaten in XCom.
- Spark MLlib ist Verarbeitung. MLlib ist weder Datenquelle noch separater Netzwerkdienst.
