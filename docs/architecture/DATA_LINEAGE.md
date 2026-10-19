# Data Lineage

## Sensoren bis zur Vorhersage

| Stufe | Identität und Nachweis | Qualitätskontrolle |
|---|---|---|
| Generator | stabiler `reading_id` aus Seed und Index; `raw/manifest.json` | deterministischer Seed, konfigurierbare Defektrate |
| MongoDB-Aufnahme | temporäre Collection, eindeutiger `reading_id`-Index | atomarer Rename erst nach vollständiger Zählung |
| Aktiver Snapshot | `pipeline_documents._id=active_sensor_snapshot` | Records, SHA-256, Batchgröße und Zeitpunkte |
| MongoDB-Export | Sortierung `reading_id ASC`; `processed/mongodb_export/manifest.json` | Quelle/Export zählen, IDs vollständig und eindeutig, SHA-256 |
| Python-Normalisierung | `processed/sensor_readings.csv` | Pflichtfelder, Timestamp, Maschinenreferenz, Wertebereiche |
| Quarantäne | Originaldokument, Zeilennummer, Reason Codes | 5.095 tolerierte Defekte separat nachvollziehbar |
| Source-Gate | Export-, Generator- und Qualitätsmanifest | kritischer Abbruch bei Mengen-, ID- oder Referenzabweichung |
| Spark-Features | `spark_transform_evidence.json`, partitioniertes Parquet | 994.905 gültige Eingaben, 4.950 Features, 50 Maschinen |
| Feature-Gate | `feature_quality_report.json` | Schlüssel/Targets vollständig, beide Klassen, purged Split ohne Datumsüberlappung |
| MLlib | `classification_benchmark.json`, `ml_report.json`, Modelle | Training/Validierung für Auswahl; unabhängiger Test |
| PostgreSQL | Unique Key mit `model_version` | Upsert ohne Verlust historischer Modellversionen |
| FastAPI | Header `X-Model-Version` und `X-Total-Count` | explizite Versionswahl, begrenzte Pagination |

## Relationale und Graph-Lineage

Maschinen, Aufträge, Wartungen und Störungen stammen aus demselben Generatorlauf. PostgreSQL schützt die Referenzen über Primär- und Fremdschlüssel. Spark verbindet Tagesaggregate per `machine_id` und `metric_date` mit Maschinen-, Wartungs- und Störungsdaten.

Die Komponenten-CSV enthält pro Maschine vier direkte Komponenten und je Produktionslinie vier geteilte Utilities. `sync_components()` materialisiert `Machine-[:HAS_COMPONENT]->Component-[:DEPENDS_ON]->Utility`. Der API-Endpunkt liest nur diese vorhandenen Beziehungen. Nachbarmaschinen bedeuten ausschließlich eine geteilte technische Utility, nicht einen bewiesenen Ausfallzusammenhang.

## Target-Lineage

`risk_label` verwendet ausschließlich den Folgetag: Ausfall, Anomalierate oder Maximalvibration. Features verwenden aktuelle oder vergangene Tageswerte. Das eintägige Target-Horizont führt zu je einem Purge-Tag an beiden Splitgrenzen. Das Gate bestätigt disjunkte Datumsbereiche und beide Klassen in allen Partitionen.

## Versions-Lineage

Die PostgreSQL-Tabelle bewahrt historische Modellversionen. `synthetic-v1` und `synthetic-v2-classification-benchmark` können parallel existieren. Die FastAPI markiert `synthetic-v2-classification-benchmark` als aktuelle Version über Konfiguration; sie bestimmt „aktuell“ nicht zufällig über das jüngste Erstellungsdatum.
