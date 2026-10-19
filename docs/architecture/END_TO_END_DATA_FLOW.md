# End-to-End-Datenfluss

## Verifizierter Produktionspfad

1. Der deterministische Generator schreibt quellorientierte CSV-, JSON- und JSONL-Dateien.
2. PostgreSQL erhält Stammdaten und Ereignisse per konfliktfestem Upsert.
3. `load_sensor_documents()` lädt die JSONL-Sensorquelle batchweise in eine temporäre MongoDB-Collection. Erst nach vollständigem Laden und Eindeutigkeitsprüfung ersetzt ein atomarer Rename die aktive Collection.
4. `pipeline_documents` hält Metadaten des aktiven Sensor-Snapshots. Die Collection ist damit kein ungenutzter Platzhalter mehr.
5. `export_sensor_documents()` liest die aktive MongoDB-Collection in Batches von 5.000, sortiert über den eindeutigen `reading_id`-Index und schreibt einen atomar veröffentlichten JSONL-Snapshot mit SHA-256-Manifest.
6. Python validiert genau diesen MongoDB-Export. Gültige Zeilen landen in der normalisierten CSV, tolerierbare Defekte mit Reason Codes in der Quarantäne.
7. Das Source-Gate vergleicht Generator-Manifest, MongoDB-Export, Qualitätsreport und die 50 Maschinenreferenzen. Kritische Abweichungen stoppen den DAG.
8. Spark liest ausschließlich den manifestierten MongoDB-Export. Der Job wendet denselben fachlichen Wertebereichs- und Referenzvertrag an, aggregiert täglich und schreibt Parquet-Features.
9. Das Feature-Gate prüft 50 Maschinen, vollständige Schlüssel und Targets, beide Klassen in Train, Validierung und Test sowie überschneidungsfreie Zeitpartitionen.
10. Erst danach laufen lokale Kennzahlen sowie MLlib-Klassifikation, lineare Regression und KMeans.
11. PostgreSQL erhält Tagesmetriken und versionierte Testprognosen. Neo4j erhält den technischen Abhängigkeitsgraphen.
12. Die finale Konsistenzprüfung kontrolliert persistierte Mengen und Modellversionen. Erst danach schreibt Airflow die Laufzusammenfassung und einen erfolgreichen `pipeline_runs`-Eintrag.
13. FastAPI liest Maschinen, Tagesmetriken, Prognosen und Läufe aus PostgreSQL. Der Abhängigkeitsendpunkt liest Neo4j per parametrisierter Cypher-Abfrage.

## Datenfluss und Verantwortlichkeiten

| Stufe | Quelle | Verarbeitung | Ziel |
|---|---|---|---|
| Synthetische Quelle | Profil, Seed | chunkweiser Python-Generator | quellorientierte Dateien plus Manifest |
| Relationale Aufnahme | CSV/JSON | psycopg, parameterisierte Upserts | PostgreSQL |
| Sensoraufnahme | JSONL | temporäre Collection, Unique Index, atomarer Rename | MongoDB `sensor_readings` |
| Snapshot-Nachweis | aktive MongoDB-Collection | sortierter Cursor, Batchgröße 5.000, SHA-256, Zählung | `processed/mongodb_export/` |
| Rohdatenqualität | MongoDB-Export plus Maschinenstamm | zentraler Qualitätsvertrag, Quarantäne | normalisierte CSV und Qualitätsreport |
| Source-Gate | drei Manifeste/Reports | Vollständigkeit, IDs, Maschinen, Ausschussquote | Airflow-Freigabe oder Abbruch |
| Feature Engineering | verifizierter Export, Stamm- und Ereignisdateien | Spark DataFrames, SQL, Joins, Windows | partitioniertes Parquet |
| Feature-Gate | Parquet-Features | Vollständigkeit, Klassen, zeitliche Splits | ML-Freigabe oder Abbruch |
| Analytik | freigegebene Features | MLlib-Klassifikation, Regression, KMeans | Modelle, Reports, JSON-Prognosen |
| Veröffentlichung | Metriken und Prognosen | konfliktfeste SQL-Upserts | PostgreSQL-Ergebnistabellen |
| Kontextgraph | Komponenten-CSV | Neo4j `MERGE` | 50 Maschinen, 220 Komponenten, 400 Beziehungen |
| Serving | PostgreSQL und Neo4j | typisierte, begrenzte Abfragen | FastAPI |

## Gemessene Full-Dataset-Mengen

| Kennzahl | Wert | Erklärung |
|---|---:|---|
| MongoDB-Sensordokumente | 1.000.000 | vollständig exportiert, keine fehlenden oder doppelten IDs |
| gültige Messungen | 994.905 | erfüllen Pflichtfelder, Zeitstempel, Maschinenreferenz und Wertebereiche |
| Quarantäne | 5.095 | 1.757 fehlende Temperaturen, 1.693 Bereichsfehler, 1.645 unbekannte Maschinen |
| tägliche Featurezeilen | 4.950 | 99 Tage × 50 Maschinen nach dem Folgetag-Target |
| Klassifikations-Testprognosen | 950 | Modellversion `synthetic-v2-classification-benchmark` |
| PostgreSQL-Prognosen vor Hardening-Lauf | 1.950 | 1.000 historische plus 950 aktuelle, unverändert vorhanden |
| Neo4j | 270 Knoten, 400 Beziehungen | 50 Maschinen, 200 direkte Komponenten, 20 geteilte Utilities |

## Modellpfad und Leakage-Schutz

Die Klassifikation verwendet den unveränderten bereinigten chronologischen 60/20/20-Split. Ein Tag zwischen Training und Validierung sowie ein Tag zwischen Validierung und Test bleibt wegen des `lead(1)`-Targets ungenutzt. Das Feature-Gate bestätigte beide Zielklassen in allen drei Partitionen. Tuning und Threshold-Optimierung bleiben auf Training und Validierung beschränkt.

Die gemessenen Testwerte bleiben unverändert: Accuracy 0,723, Macro-F1 0,534, Balanced Accuracy 0,537, PR-AUC 0,855 und ROC-AUC 0,632. Die Confusion Matrix enthält 41 TN, 187 FP, 76 FN und 646 TP. Synthetische Daten belegen keine industrielle Modellgüte.

## API-Pfad einer Vorhersage

`ml/train.py` versieht jede Prognose mit Modellname und Modellversion. `load_ml_predictions()` speichert sie unter dem eindeutigen Schlüssel aus Maschine, Datum, Modellname und Modellversion. `GET /predictions` wählt ohne Parameter ausschließlich `IIP_CURRENT_MODEL_VERSION`; eine andere Version muss der Aufrufer ausdrücklich angeben. Pagination ist auf 500 Zeilen begrenzt und die Gesamtzahl steht im Header `X-Total-Count`.

## Betriebsgrenzen

- Der MongoDB-Spark-Übergang verwendet bewusst einen kontrollierten Export statt eines zusätzlichen Connector-JARs. MongoDB bleibt die nachweisbare Quellinstanz.
- FastAPI besitzt keine Authentifizierung. Compose bindet veröffentlichte Ports deshalb standardmäßig an `127.0.0.1`.
- FastAPI führt kein Online-Scoring durch. Sie stellt persistierte Batch-Ergebnisse bereit.
- Neo4j beeinflusst die ML-Features nicht. Der Graph beantwortet ausschließlich fachliche Abhängigkeitsfragen.
- Der lokale Referenzpfad ohne Container liest weiterhin seine Generator-Datei. Der Airflow-Produktionspfad verlangt den MongoDB-Export.
