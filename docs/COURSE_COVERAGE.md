# Unterrichtsabdeckung Tage 1–20

## Einordnung

Dem Arbeitsauftrag lag kein separates, verbindliches Tagescurriculum bei. Die Zuordnung unten bildet deshalb die im Auftrag ausdrücklich genannten Big-Data-Inhalte in einer didaktisch sinnvollen Reihenfolge auf die reale Implementierung ab. Sie ist kein Ersatz für eine abweichende offizielle Tagesagenda. Jeder Nachweis verweist auf ausführbaren Code, Tests oder gespeicherte Resultate.

| Tag | Unterrichtsthema | Technologie | Konkreter Anwendungspunkt | Datei / relevante Funktionen | Ausführungs- oder Testnachweis |
|---:|---|---|---|---|---|
| 1 | Big-Data-Grundlagen und Use Case | Python, Markdown | Predictive Maintenance für 50 Maschinen und fünf Linien | `README.md`, `docs/architecture/ARCHITECTURE.md` | Full-Lauf mit 1.000.000 Messungen in `reports/latest_pipeline_run.json` |
| 2 | Linux, Projekt- und Paketstruktur | Python Packaging, Make | src-Layout, CLI, reproduzierbare Befehle | `pyproject.toml`, `Makefile`, `src/industrial_intelligence/cli.py` | `python -m pytest`: 17 schnelle Tests bestanden |
| 3 | Python-Datenverarbeitung | Python, Iteratoren, Dataclasses | Chunkweise, deterministische Datengenerierung ohne Million-Objekt-Liste | `generator.py`: `generate_dataset`, `_sensor_documents` | Generator-Unit-Tests und Full-Lauf bestanden |
| 4 | Datenformate | CSV, JSON, JSONL | Stamm-, Produktions-, Wartungs-, Störungs- und Sensordaten | `generator.py`, `models.py` | 50 Maschinen, 600 Aufträge, 320 Wartungen, 180 Störungen erzeugt |
| 5 | Relationale Modellierung | PostgreSQL 16 | Normalisierte Stamm-, Ereignis-, Metrik- und Prognosetabellen | `sql/init.sql` | Container gesund; Integrationstest bestanden |
| 6 | SQL und analytische Abfragen | PostgreSQL SQL | Joins, Gruppierungen, CTEs und fünf Industrieabfragen | `sql/industrial_queries.sql` | Reales Schema mit 50 Metrik- und 1.950 versionierten Prognosezeilen |
| 7 | Dokumentendatenbanken | MongoDB 7 | Verschachtelte Sensordokumente und Batch-Upserts | `database/mongodb.py`: `load_sensor_documents` | 1.000.000 Dokumente gezählt; Integrationstest bestanden |
| 8 | Graphdatenbanken | Neo4j 5, Cypher | Maschinen, Komponenten, Linien und technische Abhängigkeiten | `database/neo4j.py`, `cypher/schema.cypher`, `cypher/industrial_queries.cypher` | 270 Knoten und 400 Beziehungen; Integrationstest bestanden |
| 9 | ETL – Extract | Python | Lesen aus PostgreSQL-nahen CSVs, Mongo-JSONL, Wartungs-CSV und Störungs-JSON | `cli.py`: `generate_command`, `load_sources_command` | Airflow-Task `extract_industrial_data` im Full-DAG erfolgreich |
| 10 | ETL – Transform | Python | Schema-, Zeitstempel-, Bereichs-, Referenz- und Duplikatprüfung | `quality.py`: `validate_sensor_file`, `validate_reading` | 994.905 valide / 5.095 quarantänisierte Zeilen |
| 11 | ETL – Load und Idempotenz | psycopg, pymongo, Neo4j Driver | `ON CONFLICT`, Mongo-Upserts und Cypher `MERGE` | `database/postgres.py`, `mongodb.py`, `neo4j.py` | Wiederholter Full-DAG ohne Dublettenfehler; 4 Integrationstests |
| 12 | Workflow-Orchestrierung | Apache Airflow 2.10 | Zehn Tasks, Abhängigkeiten, Retry, Timeout, Quality Gate, kleine XComs | `dags/industrial_etl_dag.py` | DAG-Import fehlerfrei; vollständiger DAG-Run `success` |
| 13 | Containerisierung | Docker Compose | Getrennte, health-geprüfte Services und persistente Volumes | `compose.yaml`, `docker/*/Dockerfile` | API, Airflow, Spark und drei Datenbanken gleichzeitig gesund |
| 14 | Spark-Grundlagen und DataFrames | Spark 3.5 / PySpark | Schema-Inferenz, `select`, `filter`, `withColumn`, `dropDuplicates` | `spark_jobs/transform.py`: `build_features` | 1.000.000 Eingaben, 994.905 valide Spark-Zeilen |
| 15 | Spark SQL | Spark SQL | Temporäre View und SQL-Aggregation auffälliger Maschinen | `spark_jobs/transform.py`: `createOrReplaceTempView`, `spark.sql` | Resultat als Parquet geschrieben; Full-DAG erfolgreich |
| 16 | Spark Joins | PySpark | Sensor-Tageswerte mit Maschine, Wartung und Störung verbinden | `spark_jobs/transform.py`: `daily.join(...)` | 4.950 Feature-Zeilen für 50 Maschinen erzeugt |
| 17 | Window Functions | PySpark Window | `lag`, rollender Mittelwert, `lead` für ausschließlich zukünftige Targets, `rank` | `spark_jobs/transform.py` | Spark-Full-Lauf und chronologischer Holdout erfolgreich |
| 18 | Aggregationen und Partitionierung | PySpark, Parquet | Tagesaggregation, Verteilungsanalyse, partitioniertes Parquet | `spark_jobs/transform.py` | Parquet-Artefakte je `metric_date`; 4.950 Tagesmerkmale |
| 19 | ML-Pipelines und Evaluation | Spark MLlib | Majority-Baseline, Logistic Regression, Decision Tree, Random Forest, GBT; One-Hot-Encoding, Skalierung, Klassengewichte und Threshold-Tuning | `ml/classification.py`, `ml/metrics.py` | Finaler Test: Macro-F1 0,534 statt 0,432; beide Klassen vorhergesagt |
| 20 | Regression, Clustering und MLOps-Einordnung | MLlib | Lineare Regression, KMeans, Modellspeicherung, chronologischer Holdout; `randomSplit` nur als Lehrdemo | `ml/train.py`: `regression_report`, `clustering_report`, `split_by_time` | RMSE 0,521; Silhouette 0,362; Modelle und `ml_report.json` gespeichert |

## Ergänzende Big-Data-Themen

- **Skalierung:** Der Generator schreibt in Batches; Spark liest JSONL verteilt und schreibt partitioniertes Parquet. Eine Million Zeilen demonstriert die Strecke, ist allein aber kein wirtschaftlicher Spark-Zwang.
- **Datenqualität:** Fehler werden nicht still verworfen, sondern mit Grund in `data/quarantine/sensor_readings.jsonl` geschrieben. Das Gate erlaubt höchstens zwei Prozent Ausschuss.
- **Zeitreihenvalidierung:** Klassifikation nutzt Training, Validierung und Test chronologisch mit Purge-Tagen für den eintägigen Label-Horizont. `randomSplit` wird nur als Unterrichtskonzept gemessen und nicht als optimale Validierung ausgegeben.
- **Polyglot Persistence:** PostgreSQL hält strukturierte Fakten und Ergebnisse, MongoDB hochvolumige Sensordokumente, Neo4j technische Beziehungen.
- **Observability:** Healthchecks, Airflow-Status, Pipeline-Zusammenfassung und gespeicherte Reports liefern prüfbare Betriebsnachweise.

## Bewusst nicht umgesetzt

- **Hadoop/HDFS:** Für die lokale, containerisierte Datengröße wäre HDFS zusätzliche Komplexität ohne fachlichen Nutzen. Parquet auf einem geteilten Volume demonstriert das spaltenorientierte Format; Objekt- oder verteilte Speicherung ist ein Ausbaupunkt.
- **Kafka/Streaming:** Der Use Case arbeitet als reproduzierbarer Batch. Echtzeit-Ingestion ist als Erweiterung vorgesehen, aber nicht als implementiert behauptet.
- **Cloud Deployment:** Die Lösung ist Linux- und Docker-portabel, wurde jedoch nicht in einer Cloudumgebung ausgerollt.
- **Produktions-MLOps:** Registry, Drift-Monitoring und automatisches Retraining fehlen bewusst; synthetische Daten erlauben keine Produktionsfreigabe.
