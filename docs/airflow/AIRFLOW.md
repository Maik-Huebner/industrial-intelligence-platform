# Airflow-Orchestrierung

Der DAG `industrial_etl` läuft standardmäßig täglich um 02:00 Uhr, startet ohne Catch-up und begrenzt parallele Läufe auf eins. Jeder Task hat zwei Retries, drei Minuten Abstand und ein Timeout.

Die zehn Tasks entsprechen dem fachlichen Prozess. Nur kleine Metadatenobjekte laufen über XCom. Spark-Features, Modelle und Reports werden auf persistenten Volumes gespeichert. Airflow zeigt Logs, Retries, Timeouts und den Taskstatus in der Weboberfläche.

Manueller Start:

```bash
docker compose exec airflow-scheduler airflow dags trigger industrial_etl
docker compose exec airflow-scheduler airflow dags list-import-errors
```

Nach Container-Neustarts bleiben Datenbankvolumes, Logs und Arbeitsartefakte erhalten. Ein erneuter Lauf verwendet idempotente Ladeoperationen.

Der jüngste verifizierte Full-Lauf `manual__2026-10-19T08:00:00+00:00` endete mit `success`. `postgres_rows=1000` bezeichnet 50 lokale Maschinenmetriken plus 950 Testvorhersagen; `neo4j_rows=200` bezeichnet die eingelesenen Komponenten-CSV-Zeilen.

Das Qualitätsgate läuft im aktuellen DAG nach MLlib und Persistenz. Es entscheidet über den finalen Laufstatus, verhindert aber keine bereits erfolgten Writes. Die exakte Abhängigkeitsgrafik und diese Grenze stehen in `docs/architecture/AIRFLOW_EXECUTION_FLOW.md`.
