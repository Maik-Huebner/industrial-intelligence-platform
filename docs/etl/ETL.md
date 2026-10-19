# ETL und Datenqualität

## Extraktion und verifizierte Quelle

Der deterministische Generator erzeugt relationale CSVs, Sensor-JSONL, Wartungs-CSV, Störungs-JSON und Graph-Staging. Ein Manifest hält Profil, Seed und erwartete Mengen fest. Die Sensor-JSONL ist nur Ladequelle: Nach dem atomaren MongoDB-Load wird ausschließlich ein kontrollierter Export der aktiven Collection weiterverarbeitet.

## Zentraler Validierungsvertrag

`quality_contract.py` definiert Pflichtfelder, Sensorbereiche, erwartete Maschinenzahl und maximale Ausschussquote an einer Stelle. Python- und Spark-Pfad verwenden diese Grenzen. `quality.py` prüft Schema, IDs, Zeitstempel, Wertebereiche und Duplikate; abgewiesene Zeilen landen mit stabilem Reason Code und Originalinhalt in der Quarantäne.

## Quality Gates

Das Source Gate vergleicht Generator-, MongoDB-Export- und Qualitätsmanifest. Es stoppt bei unvollständigen Exporten, Identitätsfehlern, unerwarteter Maschinenzahl, Mengenabweichungen oder mehr als zwei Prozent Ausschuss.

Das Feature Gate läuft nach Spark und vor Metrikberechnung, ML und PostgreSQL-Persistenz. Es prüft erforderliche Spalten, 4.950 Featurezeilen, 50 Maschinen, Nullschlüssel, beide Klassen im Gesamtbestand und in jedem purged Split sowie überschneidungsfreie Datumsgrenzen.

## Spark-Transformation

Spark liest `data/processed/mongodb_export/sensor_readings.jsonl`, normalisiert mit denselben Bereichsregeln, dedupliziert und verbindet Maschinen-, Wartungs- und Störungskontext. Window Functions erzeugen `lag`, rollierende Historie und das Folgetag-Target. Die Features werden als Parquet gespeichert; der chronologische Split enthält je einen Purge-Tag an den Grenzen.

## Laden und Idempotenz

PostgreSQL verwendet `ON CONFLICT DO UPDATE`, Neo4j `MERGE` und MongoDB einen atomaren Collection-Wechsel. Wiederholte Läufe ersetzen logisch identische Ergebnisse, erhalten aber andere Modellversionen. Große Daten werden nicht über XCom übertragen; Tasks tauschen nur kleine Manifeste und Kennzahlen aus.
