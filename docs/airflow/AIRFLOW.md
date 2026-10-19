# Airflow-Orchestrierung

Der DAG `industrial_etl` läuft standardmäßig täglich um 02:00 Uhr, startet ohne Catch-up und begrenzt parallele Läufe auf eins. Tasks besitzen Retries, Retry-Abstand und Timeouts. Große Daten liegen auf persistenten Volumes; XCom enthält nur kleine Metadatenobjekte.

## 13 Tasks

1. `validate_sources`
2. `extract_industrial_data`
3. `export_mongodb_snapshot`
4. `validate_and_normalize`
5. `enforce_source_quality_gate`
6. `run_spark_transformation`
7. `enforce_feature_quality_gate`
8. `calculate_machine_metrics`
9. `run_mllib_training_and_inference`
10. `persist_postgresql_results`
11. `synchronize_neo4j_relationships`
12. `run_final_consistency_checks`
13. `generate_pipeline_summary`

Neo4j kann nach bestandenem Source Gate parallel zum Spark-Pfad synchronisiert werden. Metriken, ML und PostgreSQL-Persistenz starten erst nach bestandenem Feature Gate. Die Zusammenfassung wird erst nach finaler Prüfung von MongoDB-Quelle, PostgreSQL-Zeilen, Modellversionen und Graph-Quelle als erfolgreich gespeichert.

```bash
docker compose exec airflow-scheduler airflow dags trigger industrial_etl --run-id <run-id>
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler airflow tasks states-for-dag-run industrial_etl <run-id>
```

## Verifizierter Full-Lauf

`hardening_full_20261019T1028Z` endete am 19. Oktober 2026 mit allen 13 Tasks im Zustand `success`. Die aktive Verarbeitung vom ersten bis zum finalen Konsistenzcheck dauerte rund 2:33 Minuten. Ein einmaliger Fehler in der Summary-Task wurde durch einen korrigierten Airflow-Import behoben und danach erfolgreich wiederholt; die spätere DAG-Endzeit enthält deshalb zusätzlich den konfigurierten Retry-Abstand.

Ergebnis: 1.000.000 Quellzeilen, 994.905 gültige Zeilen, 5.095 Quarantänefälle, 4.950 Featurezeilen, 950 neue Prognosen und weiterhin 1.950 Prognosen über beide Modellversionen.
