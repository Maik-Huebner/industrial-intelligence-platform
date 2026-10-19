# Datenbanksysteme

## PostgreSQL

PostgreSQL ist System of Record für Stammdaten, Produktionskontext, aggregierte Maschinenmetriken, versionierte Prognosen und Pipeline-Läufe. `sql/init.sql` definiert Schlüssel, Checks und Indizes; Prognosen sind über `(machine_id, prediction_date, model_name, model_version)` eindeutig. Der zusätzliche Index auf Modellversion und Datum unterstützt die API-Selektion.

Der verifizierte Stand enthält 50 Maschinenmetriken sowie 1.950 Prognosen: 1.000 historische Zeilen von `synthetic-v1` und 950 Zeilen von `synthetic-v2-classification-benchmark`. Neue Läufe ersetzen nur fachlich identische Zeilen derselben Version. FastAPI liest PostgreSQL direkt und verwendet parametrisierte Abfragen mit Verbindungs- und Statement-Timeouts.

## MongoDB

MongoDB ist die verifizierte operative Quelle für Spark-Sensordaten. Der Ablauf ist bewusst zweistufig:

1. JSONL wird gestreamt und in eine temporäre Collection geladen.
2. Eindeutiger `reading_id`-Index und Dokumentzahl werden geprüft.
3. Erst dann ersetzt ein atomarer Rename die aktive Collection `sensor_readings`.
4. `pipeline_documents/_id=active_sensor_snapshot` dokumentiert Anzahl, Quell-Hash, Batchgröße und Zeitpunkte.
5. Der DAG exportiert die aktive Collection sortiert und batchweise nach `data/processed/mongodb_export/sensor_readings.jsonl`.

Die Exportdatei wird erst nach Zähl-, Missing-ID- und Duplikatprüfung atomar veröffentlicht. Das Manifest enthält Dokumentzahl, Sortierung, SHA-256 und Zeitpunkte. Spark liest ausschließlich diesen kontrollierten Snapshot. Im Full-Lauf wurden 1.000.000 Dokumente mit Batchgröße 5.000 exportiert.

## Neo4j

Neo4j ist System of Record für technischen Kontext, nicht für Messreihen. Der Graph enthält 50 Maschinen, 220 Komponenten und 400 Beziehungen. `sync_components()` verwendet Constraints und `MERGE`; eine Million Sensorwerte werden bewusst nicht als Knoten modelliert.

FastAPI beantwortet `GET /machines/{machine_id}/dependencies` über parametrisierte Cypher-Abfragen. Das Ergebnis enthält direkte Komponenten, geteilte Utilities und betroffene Nachbarmaschinen. Neo4j ist aktuell keine ML-Featurequelle.
