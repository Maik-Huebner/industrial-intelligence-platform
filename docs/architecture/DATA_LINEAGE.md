# Data Lineage

## Sensorpfad

```text
Settings(profile=full, seed=20261019)
  -> IndustrialDataGenerator.readings()
  -> data/raw/mongodb/sensor_readings.jsonl
      -> load_sensor_documents()
      -> MongoDB industrial.sensor_readings
      -> validate_sensor_file()
          -> data/processed/sensor_readings.csv
          -> data/quarantine/sensor_readings.jsonl
          -> data/processed/quality_report.json
      -> Spark build_features() liest die rohe JSONL erneut
          -> normalisierte Sensor-DataFrames
          -> Tagesaggregation
          -> Kontext-Joins und Zeitfeatures
          -> data/processed/spark_features.parquet
```

Die Python-Validierung und Spark-Normalisierung sind zwei getrennte Verarbeitungspfade. Die Python-CSV ist Eingabe der lokalen Regelbaseline; Spark verwendet die Roh-JSONL und eigene Filter.

## Stamm- und Ereignispfad

| Ursprung | Staging | Relationale Persistenz | Spark-Verwendung |
|---|---|---|---|
| `machines()` | `raw/postgres/machines.csv` | `machines` | Inner Join und statische Features |
| `_write_machines()` | `raw/postgres/production_orders.csv` | `production_orders` | keine |
| `_write_events()` | `raw/files/maintenance.csv` | `maintenance_records` | Tagesaggregation und Left Join |
| `_write_events()` | `raw/files/failures.json` | `normalized_machine_events` | Tagesaggregation und Left Join |

## Graphpfad

```text
machines()
  -> _write_components()
  -> data/raw/neo4j/machine_components.csv
  -> sync_components()
  -> (:Machine)-[:HAS_COMPONENT]->(:Component)-[:DEPENDS_ON]->(:Component)
```

Dieser Pfad endet im Graph. Weder Spark noch MLlib noch die aktuelle FastAPI lesen Neo4j.

## Feature-Herkunft

| Featuregruppe | Herkunft | Zeitbezug | Leakage-Bewertung |
|---|---|---|---|
| Temperatur, Vibration, Leistung, Last, Anomalierate | Sensormessungen des aktuellen Tages | Tag `t` | zulässig für Vorhersage von `t+1` |
| Maschinenalter, Kritikalität, Typ | Maschinenstamm | statisch | zulässig |
| Wartungsanzahl | Wartung am aktuellen Tag | Tag `t` | zulässig, sofern zum Scoring-Zeitpunkt bekannt |
| vorherige Tageswerte | `lag(1)` | `t-1` | zulässig |
| vorherige 7-Tage-Mittel und Standardabweichung | `rowsBetween(-7, -1)` | ausschließlich vor `t` | zulässig |
| 1-Tages-Änderungen und Abweichungen | aktueller Wert minus vergangener Wert | bis einschließlich `t` | zulässig |
| Wochentag Sinus/Cosinus | `metric_date` | Tag `t` | zulässig |
| `future_*` | `lead(1)` | Tag `t+1` | ausschließlich Targetbildung, explizit als Feature ausgeschlossen |
| `risk_rank` | aktuelle tägliche Rangfolge | Tag `t` | vorsorglich aus Klassifikationsfeatures ausgeschlossen |

Ein Druckmerkmal existiert nicht, weil der Generator keinen Drucksensor erzeugt.

## Klassifikations-Lineage

1. `risk_label` wird positiv, wenn am Folgetag mindestens eine Störung, eine Anomalierate über 0,08 oder eine maximale Vibration über 7,5 mm/s vorliegt.
2. `purged_chronological_split()` ordnet Daten nach Datum und entfernt den 8. sowie 28. September als Grenztage.
3. Training: 11. Juli bis 7. September, 2.950 Zeilen.
4. Validierung: 9. bis 27. September, 950 Zeilen.
5. Test: 29. September bis 17. Oktober, 950 Zeilen.
6. Während Tuning und Auswahl entstehen die Klassen­gewichte nur aus dem Training. Hyperparameter und Threshold entstehen aus Training und Validierung.
7. Das ausgewählte logistische Modell wird mit gesperrter Konfiguration auf Training plus Validierung neu gefittet; nur für diesen Refit werden die Klassen­gewichte auf der kombinierten Refit-Menge neu berechnet.
8. Der unabhängige Test erzeugt 950 Vorhersagen.

## Ergebnis-Lineage

```text
classification_best_pipeline.model
classification_benchmark.json
ml_report.json
ml_predictions_json/part-*.json
  -> PostgreSQL ml_predictions
  -> FastAPI GET /predictions liest weiterhin die JSON-Datei
```

Die JSON-Zeilen tragen `model_name=logistic_regression` und `model_version=synthetic-v2-classification-benchmark`. PostgreSQL nutzt `(machine_id, prediction_date, model_name, model_version)` als Eindeutigkeitsschlüssel. Die alte Modellversion bleibt parallel erhalten.

## Report-Priorität

1. `reports/classification_benchmark.json` ist maßgeblich für den neuen Klassifikationsvergleich.
2. `reports/classification_data_audit.json` ist maßgeblich für Split, Label-Ursachen und Korrelationen.
3. `reports/ml_report.json` verbindet den neuen Klassifikationsreport mit Regression und Clustering. Seine Top-Level-Zählung `train=3950/test=1000` gehört zum unveränderten 80/20-Pfad von Regression, nicht zum Klassifikationssplit.
4. `reports/airflow_latest.json` ist maßgeblich für den letzten Full-DAG: `postgres_rows=1000` bedeutet 50 Tagesmetriken plus 950 neue Vorhersagen.
5. `reports/execution_evidence.json` dokumentiert den früheren Stand und ist bei Klassifikation, Tests und PostgreSQL-Schreibzahlen veraltet.
