# Airflow-Orchestrierung

Der DAG `industrial_etl` läuft standardmäßig täglich um 02:00 Uhr, startet ohne Catch-up und begrenzt parallele Läufe auf eins. Jeder Task hat zwei Retries, drei Minuten Abstand und ein Timeout.

Die zehn Tasks entsprechen dem fachlichen Prozess. Nur kleine Metadatenobjekte laufen über XCom. Spark-Features, Modelle und Reports werden auf persistenten Volumes gespeichert. Airflow zeigt Logs, Retries, Timeouts und den Taskstatus in der Weboberfläche.

Manueller Start:

```bash
docker compose exec airflow-scheduler airflow dags trigger industrial_etl
docker compose exec airflow-scheduler airflow dags list-import-errors
```

Nach Container-Neustarts bleiben Datenbankvolumes, Logs und Arbeitsartefakte erhalten. Ein erneuter Lauf verwendet idempotente Ladeoperationen.

