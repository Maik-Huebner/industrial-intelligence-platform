# ETL und Datenqualität

## Extraktion

Der Generator erzeugt PostgreSQL-orientierte CSVs, MongoDB-orientierte JSONL-Dokumente, Wartungs-CSV, Störungs-JSON und Graph-Staging-CSV. Ein Manifest hält Profil, Seed und Mengen fest.

## Transformation

`quality.py` flacht Dokumente ab, prüft Pflichtfelder, IDs, Zeitstempel, numerische Bereiche und Duplikate. Abgewiesene Datensätze landen mit Zeilennummer, stabilen Reason Codes und Originaldokument in `data/quarantine/sensor_readings.jsonl`.

Spark ergänzt `lag`, rollende Temperatur, Tagesaggregation und Risikorang. Joins verbinden Maschinen, Wartungen und Störungen. Die Features landen partitioniert als Parquet.

## Laden und Idempotenz

PostgreSQL verwendet `ON CONFLICT DO UPDATE`, MongoDB `ReplaceOne(..., upsert=True)` und Neo4j `MERGE`. Wiederholte Läufe ersetzen logisch identische Ergebnisse. Der Generator öffnet Zielartefakte neu und erzeugt mit demselben Seed dieselben Daten.

