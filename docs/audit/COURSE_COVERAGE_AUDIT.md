# Audit der Unterrichtsabdeckung

Stand: 19. Oktober 2026  
Audit-Branch: `feature/final-quality-audit`  
Bewertungsschlüssel: **PASS** = implementiert und tatsächlich ausgeführt; **PARTIAL** = implementiert, aber nur teilweise geprüft; **FAIL** = nicht implementiert.

## Nachweismatrix der 13 Pflichtbereiche

| Unterrichtsthema | Implementierungsdatei | Verwendete Funktion/Technik | Fachlicher Zweck | Zugehöriger Test | Tatsächlicher Ausführungsnachweis | Ergebnis | Einschränkungen |
|---|---|---|---|---|---|---|---|
| 1. PostgreSQL | `sql/init.sql`, `database/postgres.py` | normalisiertes Schema, PK/FK, Indizes, Views, parametrisierte SQL-Abfragen, Transaktionen und Upserts | Stamm-, Produktions-, Aggregat-, Prognose- und Laufdaten | `tests/integration/test_services.py`, `tests/unit/test_api.py` | Full-Stack: 50 Maschinen, 600 Aufträge, 320 Wartungen, 180 Ereignisse, 50 Tagesmetriken, 1.950 Prognosen; Fresh-Start: 50/50/950/2 | **PASS** | Keine Hochverfügbarkeits-, Backup- oder Lastprüfung |
| 2. MongoDB | `scripts/init-mongo.js`, `database/mongodb.py` | Dokumentmodell, Unique-/Compound-Index, atomarer Collection-Tausch, sortierter Batch-Export | hochvolumige Rohsensorik und kontrollierter Spark-Snapshot | `tests/unit/test_mongodb_snapshot.py`, Integrationstest | Full-Stack: 1.000.000 Dokumente; Fresh-Start: 10.000; beide Abfragen real ausgeführt | **PASS** | Zeitstempel werden als ISO-String gespeichert; für Range-Abfragen wäre BSON Date robuster |
| 3. Neo4j | `cypher/`, `database/neo4j.py` | Constraints, `MERGE`, Maschinen-/Komponentenknoten, `HAS_COMPONENT` und `DEPENDS_ON`, parametrisierte Traversierung | technische Abhängigkeiten und Impact-Pfade | `tests/integration/test_services.py`, API-Tests | Full-Stack und Fresh-Start: 50 Maschinen, 220 Komponenten, 400 Beziehungen; API-Traversierung geprüft | **PASS** | Keine Graph-Performance- oder Mehrmandantenprüfung |
| 4. ETL Concepts | `pipeline.py`, `quality.py`, `quality_gate.py` | Staging, Validierung, reason-coded Quarantäne, Transformation, Persistenz, Lineage | kontrollierte Trennung von Roh-, gültigen und abgelehnten Daten | `test_pipeline.py`, `test_quality.py`, `test_quality_gate.py` | Full-Lauf: 1.000.000 → 994.905 valide + 5.095 Quarantäne; Fresh-Lauf: 10.000 → 9.943 + 57 | **PASS** | Synthetische Fehlerverteilung ersetzt keine reale Datenprofilierung |
| 5. ETL with Python | `generator.py`, `pipeline.py`, `database/*.py` | Generatoren/Streaming, `csv`, JSON/JSONL, dataclasses/Pydantic, Adapter, Batch-Verarbeitung | reproduzierbare Erzeugung und Integration heterogener Quellen | Generator-, Pipeline-, Qualitäts- und Adaptertests | lokaler Full-Report sowie zwei isolierte Small-DAG-Läufe erfolgreich | **PASS** | Hostpfad nutzt für Scoring bewusst nur eine Regel-Baseline, nicht MLlib |
| 6. Airflow Basics | `dags/industrial_etl_dag.py` | DAG, TaskFlow-API, Schedule, Retries, Timeouts, XCom-Metadaten, `max_active_runs=1` | Orchestrierung und Betriebsnachweis | DAG-Importprüfung, Containerintegration | keine Importfehler; DAG im Scheduler geladen; reale Task-Instanzen geprüft | **PASS** | Kein externer Alerting-Kanal konfiguriert |
| 7. Airflow ETL Pipeline | `dags/industrial_etl_dag.py` | 13 Tasks, explizite Abhängigkeiten, Source-/Feature-Gate, DB-Ladevorgänge | vollständige End-to-End-Steuerung bis API-fähiger Persistenz | E2E- und Integrationstests | `hardening_full_20261019T1028Z`: 13/13 erfolgreich; isoliert zusätzlich geplanter und manueller Lauf 13/13 | **PASS** | Ein isolierter Transform-Task benötigte wegen knapper Parallelressourcen einen Retry; danach erfolgreich |
| 8. Spark Basics | `spark_jobs/transform.py`, Compose-Dienste | `SparkSession`, Master/Worker, Transformationen, Actions, persistierte Artefakte | verteilbarer Verarbeitungspfad für Sensor- und Stammdaten | `tests/spark/test_validation_contract.py` | Spark 3.5.3-Container, Full-DAG und zwei isolierte Runs ausgeführt; Vertragscheck im identischen Container bestanden | **PASS** | Keine belastbare Skalierungs- oder Performanceaussage aus nur 1 Mio. Zeilen |
| 9. Spark DataFrames | `spark_jobs/transform.py`, `ml/*.py` | Schemas, `select`, `withColumn`, `filter`, `groupBy`, DataFrame-Writer | typisierte Aufbereitung und Feature-Bildung | Spark-Vertragstest, Feature-Gate | 4.950 Featurezeilen und 50 Maschinen im Full-Lauf; Null-Key-/Target-Prüfung bestanden | **PASS** | Hosttest ohne PySpark übersprungen; Containerpfad ist die Sollumgebung |
| 10. Spark SQL | `spark_jobs/transform.py` | temporäre Views und `spark.sql` | SQL-basierte Verdichtung und didaktischer Vergleich zum DataFrame-Pfad | Spark-Vertragstest/E2E | im realen Spark-Job ausgeführt; Ergebnis durch Feature-Gate und Persistenz verifiziert | **PASS** | Kein eigener SQL-Performancevergleich |
| 11. Spark Joins & Window Functions | `spark_jobs/transform.py`, `ml/classification.py` | Inner/Left Joins, `Window`, `lag`, `lead`, rückwärtsgerichtete 7-Tage-Fenster | Kontextanreicherung, Änderungen, rollende Historie und Folgetagsziele | Spark-Vertragstest; Split-Regressionstest | Full-ML-Lauf ausgeführt; purged 60/20/20 und korrigierter purged 80/20-Split belegt | **PASS** | `lead` dient ausschließlich Labels/Ziel und wird aus Features ausgeschlossen |
| 12. Spark Aggregations | `spark_jobs/transform.py` | `groupBy`, `avg`, `stddev`, `max`, Counts und rollende Mittelwerte | tägliche Maschinen- und Linienkennzahlen | Feature-Gate, E2E-Test | 4.950 Tagesfeatures, 50 aktuelle Maschinenmetriken; reproduzierbare Counts | **PASS** | Tagesauflösung glättet kurzfristige Spitzen |
| 13. Spark MLlib | `ml/train.py`, `ml/classification.py`, `ml/metrics.py` | `VectorAssembler`, `StringIndexer`, `OneHotEncoder`, `StandardScaler`, `Pipeline`, Logistic/Tree/Forest/GBT, LinearRegression, KMeans, Evaluatoren | Klassifikation, Prognose und explorative Segmentierung | Metrik-Unit-Tests, Spark-Vertragstest, E2E | Full-Training real ausgeführt; Modellvergleich, Regression und KMeans in `reports/ml_report.json` | **PASS** | Klassifikation trennt nur schwach; Cluster sind nicht fachlich validiert |

## Unterthemenprüfung

Im Repository lagen keine fremden Unterrichtsnotebooks oder zusätzlichen verbindlichen Lehrpläne vor. Deshalb wurden ausschließlich die im Workorder genannten Pflicht- und Spark-Unterthemen bewertet. Folgende konkret geforderte Techniken wurden im Code nachgewiesen:

- PostgreSQL: relationales Modell, referenzielle Integrität, Indizes, View und parametrisierte Abfragen.
- MongoDB: Dokumente, Indexierung, Bulk-/Batch-Verarbeitung und konsistenter Snapshot.
- Neo4j: Property Graph, Constraints, Knoten, Beziehungen und Traversierung.
- Airflow: DAG/Tasks, Scheduling, Abhängigkeiten, Retry/Timeout und Qualitätsgates.
- Spark: Session, DataFrames, SQL, Views, Inner/Left Join, `lag`, `lead`, rollende Fenster, Aggregation, Parquet und Partitionierung.
- MLlib: Transformer, Estimatoren, Pipelines, Klassifikation, Regression, Clustering und mehrere Evaluationsmetriken.

## Gesamtbewertung

Alle 13 verbindlichen Themen sind **vollständig implementiert und in der vorgesehenen Containerumgebung ausgeführt**. Die Bewertung besagt nicht, dass jedes Thema produktionsreif oder in voller Breite behandelt ist. Nicht belegt sind insbesondere Cluster- oder Datenbank-Benchmarks, Hochverfügbarkeit und reale industrielle Modellgüte.
