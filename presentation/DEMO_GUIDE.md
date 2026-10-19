# Live- und Fallback-Demo

## Live-Demo in 90 Sekunden

Voraussetzung: `.env` aus `.env.example`, laufender Docker-Stack. Bei Portkonflikten die Host-Portvariablen in `.env` ändern.

1. Services zeigen:

   ```bash
   docker compose ps
   ```

   Erwartung: Datenbanken, API, Airflow-Webserver und Spark Master sind gesund; Scheduler und Worker laufen.

2. API-Status prüfen:

   ```bash
   curl -s http://localhost:8000/health
   ```

   Erwartung: `status=ok`, Pipeline-Artefakte verfügbar.

3. Zwei Prognosen zeigen:

   ```bash
   curl -s 'http://localhost:8000/predictions?risk=high' | python -m json.tool | head -40
   ```

   Danach `reports/classification_benchmark.json` öffnen und die finale Confusion Matrix 41 / 187 / 76 / 646 zeigen.

4. Airflow öffnen: `http://localhost:8080`, DAG `industrial_etl`. 13 Tasks und letzten erfolgreichen Lauf zeigen.

5. Optional Neo4j Browser öffnen und ausführen:

   ```cypher
   MATCH (m:Machine)-[:HAS_COMPONENT]->(c:Component)
   RETURN m.machine_id, collect(c.component_type)[0..5]
   LIMIT 5;
   ```

## Fallback-Demo ohne laufende Container

Alle Zahlen sind echte, am 19. Oktober 2026 erzeugte Ausführungsergebnisse:

1. `reports/execution_evidence.json` öffnen: kompakter, maschinenlesbarer Abnahmenachweis.
2. `reports/airflow_latest.json` öffnen: Full-DAG `success`, 994.905 valide und 5.095 verworfene Messungen, 1.000 PostgreSQL-Schreibvorgänge (50 Tagesmetriken plus 950 neue Testprognosen), 200 synchronisierte Graph-Quellzeilen.
3. `reports/classification_benchmark.json` öffnen: fünf Klassifikatoren, purged 60/20/20-Split, klassenweise Metriken und finale Confusion Matrix.
4. `reports/ml_report.json` öffnen: Klassifikation, purged Regression und Clusterprofile.
5. `reports/latest_pipeline_run.json` öffnen: lokaler Full-Lauf in 14,862 Sekunden sowie Top-Risikomaschinen.

Kernausgabe:

```text
Generator      1.000.000 Sensormessungen
Qualität         994.905 valide | 5.095 Quarantäne
Spark              4.950 Tagesfeature-Zeilen
MLlib                  950 neue Testprognosen
MongoDB         1.000.000 Sensordokumente
Neo4j                 270 Knoten | 400 Beziehungen
Airflow            Full-DAG erfolgreich
Tests              32 inklusive Containerintegration bestanden
```

## Wenn etwas schiefgeht

- Port belegt: Host-Port in `.env` ändern; interne Ports nicht ändern.
- Airflow noch nicht bereit: auf den Healthcheck warten und die Fallback-Dateien zeigen.
- Spark-Demo zu lang: keinen Full-Lauf während des Vortrags starten. Den gespeicherten Nachweis zeigen und `small` nur bei genügend Zeit verwenden.
- Keine Daten: `make pipeline PROFILE=small` liefert lokal eine schnelle, transparente Baseline; sie ist nicht das MLlib-Modell.
