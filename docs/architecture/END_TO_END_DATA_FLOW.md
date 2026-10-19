# End-to-End-Datenfluss

## Prüfgrundlage

Diese Beschreibung basiert auf dem Stand des Branches `feature/classification-benchmark` nach Commit `29a3636`. Sie unterscheidet zwei Nachweisarten:

- **im Code nachgewiesen:** Implementierung, Konfiguration oder Schema ist im Repository vorhanden;
- **im Lauf verifiziert:** gespeicherter Report, Datenartefakt, API-Abruf oder direkte Read-only-Abfrage bestätigt die Ausführung.

Der Full-DAG vom 19. Oktober 2026 endete laut Airflow mit `state=success`. Die aktuelleren Klassifikationsartefakte haben Vorrang vor `reports/execution_evidence.json`, dessen Klassifikations- und Testzahlen noch den älteren Lauf `synthetic-v1` beschreiben.

## Tatsächliche Pipeline-Reihenfolge

1. `IndustrialDataGenerator.generate()` erzeugt deterministische Quelldateien für Stammdaten, Aufträge, Wartung, Störungen, Komponenten und Sensormessungen.
2. `load_source_data()` lädt relationale Quellen per Upsert nach PostgreSQL. `load_sensor_documents()` lädt die JSONL-Sensordokumente unabhängig davon per MongoDB-Upsert.
3. `validate_sensor_file()` flacht die JSON-Dokumente ab, prüft sie und schreibt gültige Zeilen als CSV sowie ungültige Originaldokumente mit Reason Codes in die Quarantäne.
4. Spark liest für seinen Rechenpfad die rohe JSONL-Datei erneut. Der Spark-Job verwendet nicht die normalisierte CSV als Eingabe, sondern implementiert eigene Filter und Deduplizierung.
5. `build_features()` aggregiert Sensorwerte je Maschine und Tag, verbindet Maschinen-, Wartungs- und Störungsdaten und schreibt Parquet-Features.
6. `run_classification_benchmark()` vergleicht fünf Klassifikatoren. `regression_report()` und `clustering_report()` führen die unveränderten Regressions- und KMeans-Pfade aus.
7. Spark schreibt das ausgewählte Klassifikationsmodell, JSON-Testvorhersagen und Reports auf gemeinsame Volumes.
8. `load_machine_metrics()` und `load_ml_predictions()` persistieren lokale Maschinenkennzahlen und Spark-Testvorhersagen in PostgreSQL.
9. `sync_components()` schreibt Maschinen, Komponenten und geteilte Abhängigkeiten per `MERGE` nach Neo4j. Der Graph liefert keine Features an MLlib.
10. FastAPI liest Maschinen, lokale Kennzahlen, Spark-Vorhersagen und den letzten lokalen Pipelinebericht direkt aus Dateien. Die API liest aktuell keine Datenbank.

## Vollständige Datenfluss-Tabelle

| Schritt | Quelle | Technologie | Verarbeitung | Ziel | Implementierungsnachweis |
|---|---|---|---|---|---|
| 1. Laufkonfiguration | Environment, CLI-Argument | Python | Profil, Seed, Datenverzeichnis, Chunkgröße und Fehlerquote auflösen | `Settings` | `src/industrial_intelligence/config.py`, `Settings.from_env()` |
| 2. Maschinenstamm | Seed und feste Regeln | Python | 50 Maschinen auf fünf Linien mit Typ, Baujahr, Kritikalität und Hersteller erzeugen | `data/raw/postgres/machines.csv` | `generator.py`, `IndustrialDataGenerator.machines()` |
| 3. Produktionsaufträge | Seed `+11` | Python | 600 Aufträge mit stabilen IDs und Status erzeugen | `data/raw/postgres/production_orders.csv` | `generator.py`, `_write_machines()` |
| 4. Wartungen und Störungen | Seed `+23` | Python | 320 Wartungen und 180 Störungen erzeugen | CSV und JSON unter `data/raw/files/` | `generator.py`, `_write_events()` |
| 5. Komponenten | Maschinenliste | Python | Vier direkte Komponenten pro Maschine und geteilte Utility-Abhängigkeiten referenzieren | `data/raw/neo4j/machine_components.csv` | `generator.py`, `_write_components()` |
| 6. Sensormessungen | Seed `20261019`, Profil `full` | Python | Temperatur, Vibration, Leistung, Last, Szenario und gezielte Qualitätsfehler erzeugen | `data/raw/mongodb/sensor_readings.jsonl` | `generator.py`, `readings()`, `generate()` |
| 7. Relationale Quellen laden | Maschinen-, Auftrags-, Wartungs- und Störungsdateien | PostgreSQL, psycopg | Batch-Insert mit `ON CONFLICT DO UPDATE`; Störungen als normalisierte Events | vier PostgreSQL-Tabellen | `database/postgres.py`, `load_source_data()` |
| 8. Sensordokumente laden | JSONL-Sensordatei | MongoDB, PyMongo | `ReplaceOne`-Upserts in Batches von 5.000 anhand `reading_id` | `industrial.sensor_readings` | `database/mongodb.py`, `load_sensor_documents()` |
| 9. Python-Validierung | JSONL und Maschinen-CSV | Python | Flattening, Pflichtfelder, Wertebereiche, Timestamp, Maschinenreferenz und Duplikate prüfen | validierte CSV, Quarantäne-JSONL, Qualitätsreport | `quality.py`, `validate_sensor_file()` |
| 10. Lokale Referenzmetriken | validierte CSV, Wartungs-CSV, Störungs-JSON | Python | Streaming-Aggregation über die gesamte Historie und transparente Regelbewertung | `machine_metrics.csv`, `predictions.json` | `pipeline.py`, `calculate_metrics()` |
| 11. Spark-Normalisierung | rohe Sensor-JSONL | Spark DataFrame | verschachtelte Felder auswählen, casten, filtern und nach `reading_id` deduplizieren | normalisierter DataFrame | `spark_jobs/transform.py`, `build_features()` |
| 12. Tagesaggregation | normalisierter DataFrame | Spark DataFrame | `groupBy(machine_id, metric_date)` und Aggregationen | Tageswerte | `build_features()` |
| 13. Kontext-Joins | Tageswerte, Maschinen-CSV, Wartungs-CSV, Störungs-JSON | Spark | Inner Join für Maschinen, Left Joins für Ereignisse | angereicherte Tageswerte | `build_features()` |
| 14. Historische Features | angereicherte Tageswerte | Spark Window | `lag`, ausschließlich vergangene 7-Tage-Fenster, Änderungen und Abweichungen | leakage-arme Features | `build_features()`, `rowsBetween(-7, -1)` |
| 15. Folgetag-Targets | angereicherte Tageswerte | Spark Window | `lead(1)` für Temperatur, Ausfall, Anomalierate und Maximalvibration | Regressions- und Klassifikationsziel | `build_features()` |
| 16. Linienanalyse | temporäre View `machine_features` | Spark SQL | Gruppierung je Linie und Tag | `line_daily_metrics.parquet` | `createOrReplaceTempView()`, `spark.sql()` |
| 17. Feature-Persistenz | Feature-DataFrame | Parquet | Sortierung und Partitionierung nach `metric_date` | `spark_features.parquet` | `build_features()` |
| 18. Klassifikation | Parquet-Features | Spark MLlib | purged 60/20/20-Split, Klassen­gewichte, Encoding, Skalierung, fünf Modelle, Threshold-Tuning | Benchmark, finales Modell, 950 Testvorhersagen | `ml/classification.py`, `run_classification_benchmark()` |
| 19. Regression | Parquet-Features | Spark MLlib | chronologischer 80/20-Split, lineare Regression und Mittelwert-Baseline | Regressionsreport und Modell | `ml/train.py`, `regression_report()` |
| 20. Clustering | Trainingspartition | Spark MLlib | Skalierung und KMeans mit `k=3` | Clusterreport und Modell | `ml/train.py`, `clustering_report()` |
| 21. Vorhersagen laden | Spark-JSON-Ausgabeverzeichnis | PostgreSQL | Upsert nach Maschine, Datum, Modellname und Modellversion | `ml_predictions` | `database/postgres.py`, `load_ml_predictions()` |
| 22. Graph synchronisieren | Komponenten-CSV | Neo4j | `Machine`, direkte und geteilte `Component`-Knoten sowie zwei Beziehungstypen per `MERGE` | technischer Abhängigkeitsgraph | `database/neo4j.py`, `sync_components()` |
| 23. Qualitätsgate | Python-Qualitätsreport | Airflow | Lauf abbrechen, wenn keine gültigen Daten oder mehr als zwei Prozent Ausschuss | Taskstatus und kompakte Summary | `dags/industrial_etl_dag.py`, `run_data_quality_checks()` |
| 24. API-Ausgabe | CSV- und JSON-Artefakte auf `/opt/iip/data`, lokaler Report unter `reports/` | FastAPI | Dateien lesen, optional nach vorhergesagtem Label filtern | REST-Responses | `api/main.py` |

## Datenmengen und ihre Bedeutung

| Wert | Bedeutung | Nachweis |
|---|---|---|
| 50 | Maschinenstammsätze; zugleich 50 `Machine`-Knoten in Neo4j | Manifest, PostgreSQL- und Neo4j-Abfrage |
| 600 | Produktionsaufträge | Manifest und PostgreSQL-Abfrage |
| 1.000.000 | erzeugte JSONL-Sensordokumente und MongoDB-Dokumente | Manifest und MongoDB-Abfrage |
| 994.905 | von Python und Spark akzeptierte Messungen | `quality_report.json`, Airflow-Summary und Spark-Report |
| 5.095 | quarantänisierte Messungen | 1.757 fehlende Temperaturen, 1.693 Bereichsverletzungen, 1.645 unbekannte Maschinen |
| 4.950 | 99 Featuretage mal 50 Maschinen | Parquet-Partitionen und ML-Report |
| 220 | Neo4j-`Component`-Knoten: 200 direkte Komponenten plus 20 geteilte Utilities | Neo4j-Abfrage |
| 270 | alle aktuell vorhandenen Neo4j-Knoten: 220 Komponenten plus 50 Maschinen | Neo4j-Abfrage |
| 400 | 200 `HAS_COMPONENT`- und 200 `DEPENDS_ON`-Beziehungen | Neo4j-Abfrage |
| 950 | Testvorhersagen der Modellversion `synthetic-v2-classification-benchmark` | JSON-Partdatei, PostgreSQL und API |
| 1.950 | aktuell insgesamt gespeicherte PostgreSQL-Vorhersagen: 1.000 alte plus 950 neue | PostgreSQL-Abfrage |

Die 4.950 Featurezeilen entstehen, weil jede der 50 Maschinen tägliche Werte besitzt. Die Messungen decken 100 Kalendertage ab. Das Folgetag-Target benötigt `lead(1)`; deshalb entfällt je Maschine der letzte Tag. Übrig bleiben 99 Tage mal 50 Maschinen.

## MLlib-Klassifikation

Der Split enthält 2.950 Trainings-, 950 Validierungs- und 950 Testzeilen. Der 8. und 28. September sind Purge-Tage und gehören zu keiner Partition. Während Tuning und Auswahl stammen die Klassen­gewichte ausschließlich aus dem Training. Hyperparameter und der Schwellenwert 0,58 werden auf Training und Validierung bestimmt. Erst nach dem Lock der Konfiguration wird das finale Modell auf Training plus Validierung neu gefittet; dafür werden die Gewichte auf dieser kombinierten Refit-Menge neu berechnet. Der Test fließt in keine dieser Entscheidungen ein.

Der verifizierte finale Test erreicht Accuracy 0,723, Macro-F1 0,534, Balanced Accuracy 0,537, PR-AUC 0,855 und ROC-AUC 0,632. Die Confusion Matrix lautet 41 TN, 187 FP, 76 FN und 646 TP. Der Recall der Klasse 0 beträgt nur 0,180. Das Modell trennt beide Klassen besser als die Majority-Baseline, erreicht aber keine Produktionsreife.

## Tatsächlicher API-Pfad einer MLlib-Vorhersage

1. MLlib berechnet `risk_probability` und wendet den validierungsbasierten Threshold an.
2. `ml/train.py` schreibt 950 JSON-Zeilen nach `data/processed/ml_predictions_json/`.
3. Airflow lädt dieselben Zeilen zusätzlich in PostgreSQL.
4. `GET /predictions` liest aktuell die JSON-Partdateien auf dem gemeinsamen Volume, nicht die PostgreSQL-Tabelle.
5. Der Query-Parameter `risk=high` filtert `predicted_label == 1`; jeder andere nichtleere Wert wird wie Klasse 0 behandelt.

Damit ist PostgreSQL ein Ergebnisarchiv, aber noch nicht die Serving-Quelle der API.

## Nachgewiesene Grenzen

- MongoDB ist persistente Rohdatenablage, aber Spark liest die JSONL-Stagingdatei und nicht die MongoDB-Collection.
- Die Python-Validierung erzeugt eine normalisierte CSV, die Spark nicht als Eingabe nutzt. Spark führt einen parallelen Filterpfad aus.
- Neo4j liegt außerhalb des Vorhersagepfads. Die vorhandene API bietet keinen Graph-Endpunkt.
- Das Airflow-Qualitätsgate läuft nach MLlib-Training und Ergebnis-Persistenz. Ein Gate-Fehler würde den DAG als fehlgeschlagen markieren, aber nicht verhindern, dass vorherige Tasks bereits geschrieben haben.
- `pipeline_documents` in MongoDB ist angelegt, aktuell jedoch leer und ungenutzt.
- `Pivot` wird im Spark-Job nicht verwendet.
- Die API besitzt keine Authentifizierung, keine Pagination für Vorhersagen und keine deklarativen Pydantic-Response-Modelle.
- Alle Daten und Labels sind synthetisch. Die gemessene Modellgüte belegt keine reale Wartungsleistung.
