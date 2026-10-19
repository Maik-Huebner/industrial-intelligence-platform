# Airflow-Ausführungsfluss

## Task-Reihenfolge

| Nr. | Task | Zweck | Kritische Wirkung |
|---:|---|---|---|
| 1 | `validate_sources` | Profil und gemeinsames Datenvolume vorbereiten | Infrastrukturfehler stoppen früh |
| 2 | `extract_industrial_data` | Quellen generieren, PostgreSQL laden, MongoDB-Snapshot atomar veröffentlichen | letzte vollständige Mongo-Collection bleibt bei Ladefehler erhalten |
| 3 | `export_mongodb_snapshot` | aktive Collection sortiert und batchweise exportieren | Zählungs-/ID-Fehler verhindern Veröffentlichung des Exports |
| 4 | `validate_and_normalize` | MongoDB-Export prüfen und Quarantäne schreiben | tolerierbare Einzeldefekte bleiben getrennt |
| 5 | `enforce_source_quality_gate` | Mengen, IDs, Referenzen, Maschinenzahl und Ausschussquote prüfen | stoppt vor Spark und ML |
| 6 | `run_spark_transformation` | tägliche Features aus dem verifizierten Export berechnen | schreibt Parquet und Evidenzreport |
| 7 | `enforce_feature_quality_gate` | Features, Klassen und zeitliche Splits prüfen | stoppt vor jedem Training und vor Veröffentlichung |
| 8 | `calculate_machine_metrics` | transparente Python-Kennzahlen erzeugen | läuft nur nach beiden Gates |
| 9 | `run_mllib_training_and_inference` | Klassifikation, Regression und KMeans ausführen | läuft nur nach beiden Gates |
| 10 | `persist_postgresql_results` | Metriken und versionierte Prognosen upserten | wartet auf Metriken und MLlib |
| 11 | `synchronize_neo4j_relationships` | Komponenten und Utilities per `MERGE` synchronisieren | läuft nach Source-Gate |
| 12 | `run_final_consistency_checks` | PostgreSQL-Mengen, Modellversionen und Graph-Quelle prüfen | verhindert erfolgreichen Laufstatus bei Teilveröffentlichung |
| 13 | `generate_pipeline_summary` | Summary und erfolgreichen `pipeline_runs`-Datensatz schreiben | markiert erst nach finaler Konsistenz erfolgreich |

## Abhängigkeitsgraph

```text
validate_sources
  └─ extract_industrial_data
      └─ export_mongodb_snapshot
          └─ validate_and_normalize
              └─ enforce_source_quality_gate
                  ├─ run_spark_transformation
                  │   └─ enforce_feature_quality_gate
                  │       ├─ calculate_machine_metrics ─┐
                  │       └─ run_mllib_training_and_inference ─┤
                  │                                             └─ persist_postgresql_results ─┐
                  └─ synchronize_neo4j_relationships ──────────────────────────────────────────┤
                                                                                               └─ run_final_consistency_checks
                                                                                                   └─ generate_pipeline_summary
```

## Fehlerklassen

- **Tolerierbare Rohdatenfehler:** einzelne fehlende Temperaturen, unzulässige Werte oder unbekannte Maschinen landen mit Reason Code in Quarantäne. Bis zwei Prozent Ausschuss sind zulässig.
- **Kritische Integritätsfehler:** unvollständiger Export, doppelte IDs, falsche Maschinenzahl, fehlende Zielklasse, unvollständige Features oder Split-Überlappung brechen den Lauf vor ML beziehungsweise Veröffentlichung ab.
- **Infrastrukturfehler:** nicht erreichbare Datenbank, Spark-Fehler oder Dateisystemfehler schlagen fehl und unterliegen den konfigurierten Retries und Timeouts.

Große Daten verbleiben auf dem gemeinsamen Volume. XCom transportiert nur kompakte Manifeste, Reports und Zählungen.
