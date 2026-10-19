# Datenbanksysteme

## PostgreSQL

`sql/init.sql` definiert Primär- und Fremdschlüssel, Checks, Eindeutigkeiten, Indizes und die View `machine_risk_overview`. `sql/industrial_queries.sql` enthält fünf fachliche Analysen sowie INSERT, UPDATE, DELETE und `EXPLAIN (ANALYZE, BUFFERS)`. Ergebnis-Upserts verwenden den fachlichen Schlüssel `(machine_id, metric_date)`.

ML-Vorhersagen verwenden den Eindeutigkeitsschlüssel `(machine_id, prediction_date, model_name, model_version)`. Aktuell liegen 1.000 Zeilen der älteren Version und 950 Zeilen der Benchmark-Version gleichzeitig vor. Die FastAPI liest diese Tabelle derzeit nicht.

## MongoDB

Sensordokumente enthalten verschachtelte Werte und Einheiten, Betriebskontext und Lineage. Indizes decken `reading_id`, Maschine/Zeit sowie Szenario/Maschine ab. Der Adapter verwendet ungeordnete `bulk_write`-Upserts. Eine Aggregation nutzt `$match`, `$group`, `$project` und `$sort`. `$unwind` und `$lookup` sind für diese bewusst denormalisierte Rohquelle fachlich nicht nötig. Spark übernimmt die systemübergreifenden Joins, liest dafür aber aktuell die JSONL-Stagingdatei und nicht direkt MongoDB. Die initialisierte Collection `pipeline_documents` ist leer und ungenutzt.

## Neo4j

Der ausgeführte Graphpfad modelliert 50 Maschinen und 220 Komponenten mit 400 Beziehungen. `sync_components()` erzeugt `Machine`, direkte `Component`-Knoten und geteilte Utility-`Component`-Knoten. `cypher/schema.cypher` enthält darüber hinaus Constraints und Beispiele für Factory, ProductionLine, Sensor und MaintenanceTask; diese Datei wird von Compose und DAG nicht automatisch ausgeführt. `cypher/industrial_queries.cypher` zeigt gemeinsame Abhängigkeiten, kürzeste Pfade und Wartungsaggregation. Neo4j ist aktuell weder ML-Featurequelle noch API-Datenquelle.
