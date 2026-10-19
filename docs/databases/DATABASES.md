# Datenbanksysteme

## PostgreSQL

`sql/init.sql` definiert Primär- und Fremdschlüssel, Checks, Eindeutigkeiten, Indizes und die View `machine_risk_overview`. `sql/industrial_queries.sql` enthält fünf fachliche Analysen sowie INSERT, UPDATE, DELETE und `EXPLAIN (ANALYZE, BUFFERS)`. Ergebnis-Upserts verwenden den fachlichen Schlüssel `(machine_id, metric_date)`.

## MongoDB

Sensordokumente enthalten verschachtelte Werte und Einheiten, Betriebskontext und Lineage. Indizes decken `reading_id`, Maschine/Zeit sowie Szenario/Maschine ab. Der Adapter verwendet ungeordnete `bulk_write`-Upserts. Eine Aggregation nutzt `$match`, `$group`, `$project` und `$sort`. `$unwind` und `$lookup` sind für diese bewusst denormalisierte Rohquelle fachlich nicht nötig; Spark übernimmt die systemübergreifenden Joins.

## Neo4j

Der Graph modelliert Fabrik, Linien, Maschinen, Komponenten, Sensoren und Wartungsaufgaben. `cypher/schema.cypher` setzt Constraints. `cypher/industrial_queries.cypher` zeigt gemeinsame Abhängigkeiten, kürzeste Pfade und Wartungsaggregation. Pfadfragen bleiben verständlicher als rekursive Self-Joins in PostgreSQL, während Massensensordaten bewusst außerhalb des Graphen liegen.

