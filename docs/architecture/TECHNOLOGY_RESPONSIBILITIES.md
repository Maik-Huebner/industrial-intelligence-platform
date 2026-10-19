# Technologieverantwortlichkeiten

## Warum mehrere Technologien eingesetzt werden

Die Plattform verwendet mehrere Systeme nicht wegen einer künstlichen Technologiequote, sondern weil die Datenformen unterschiedliche Anforderungen haben. Der aktuelle Stand zeigt zugleich, wo die Integration bewusst endet.

| Technologie | Tatsächliche Verantwortung | Warum passend | Nicht ihre Aufgabe im aktuellen System |
|---|---|---|---|
| Python | Generator, Dateiverarbeitung, Validierung, CLI, lokale Baseline und Adapter | deterministische Logik, Streaming über Dateien und gute Testbarkeit | keine verteilte Verarbeitung der Million Messungen |
| PostgreSQL | normalisierte Stamm-, Auftrags-, Wartungs-, Störungs-, Tagesmetrik- und Vorhersagetabellen | Constraints, Foreign Keys, ACID und SQL-Abfragen | keine Rohsensorhistorie; aktuell keine API-Serving-Quelle |
| MongoDB | vollständige verschachtelte Sensordokumente mit Einheiten, Kontext und Lineage | Dokumentform passt ohne relationale Aufspaltung; Batch-Upserts und flexible Felder | Spark liest nicht direkt aus MongoDB; keine ML-Ergebnispersistenz |
| Neo4j | Maschinen, Komponenten und geteilte technische Abhängigkeiten | Pfade und gemeinsame Abhängigkeiten lassen sich in Cypher direkt ausdrücken | keine Rohmessungen, keine Modellfeatures und aktuell keine API-Ausgabe |
| Apache Spark | Filterung, Deduplizierung, Tagesaggregation, Joins, Windows, SQL und Parquet | reproduzierbarer DataFrame-Pfad, verteilbare Berechnung und Unterrichtsnachweis | kein Orchestrator und kein dauerhaftes Datenbanksystem |
| Spark MLlib | Training und Bewertung von Klassifikation, Regression und Clustering | Pipelines verbinden Feature-Vorbereitung und Modell; Spark-Daten bleiben im selben Rechenpfad | keine Modellregistry, kein Online-Inference-Service |
| Apache Airflow | Reihenfolge, Retries, Timeouts, Taskstatus und kompakte Laufzusammenfassung | Batch-Abhängigkeiten und Betriebsnachvollziehbarkeit | kein Datenspeicher; große Datensätze laufen nicht über XCom |
| FastAPI | lesende HTTP-Ausgabe der erzeugten Artefakte | kleine, klare Demonstrationsschnittstelle | keine Datenbankabstraktionsschicht, keine Authentifizierung, kein Online-Scoring |
| Docker Compose | reproduzierbare lokale Services, Netzwerk, Healthchecks und Volumes | einheitliche Entwicklungs- und Demonstrationsumgebung | kein Produktionsorchestrator wie Kubernetes |
| Parquet | partitionierter Feature- und Linienmetrik-Speicher | spaltenorientiert, Spark-nativ und für spätere Analysen geeignet | kein transaktionales System |

## PostgreSQL im Detail

`sql/init.sql` definiert zehn fachliche Tabellen sowie die View `machine_risk_overview`. Primär- und Fremdschlüssel verbinden Werk, Linien, Maschinen, Aufträge, Wartungen, Events, Tagesmetriken, Vorhersagen und Pipeline-Läufe. Der Schlüssel der Vorhersage umfasst Maschine, Datum, Modellname und Modellversion. Deshalb konnten `synthetic-v1` mit 1.000 Zeilen und `synthetic-v2-classification-benchmark` mit 950 Zeilen gleichzeitig erhalten bleiben.

Die API verwendet derzeit keine dieser Tabellen. Ihre `depends_on`-Einträge stellen nur sicher, dass die drei Datenbankcontainer gesund sind, bevor die App startet.

## MongoDB im Detail

`sensor_readings` enthält eine Million Dokumente. Jedes Dokument enthält `reading_id`, `machine_id`, Zeitstempel, verschachtelte Sensorwerte samt Einheit, Betriebskontext und Lineage. Ein Unique Index schützt `reading_id`; weitere Indizes unterstützen Maschine/Zeit und Szenario/Maschine. `ReplaceOne(..., upsert=True)` verhindert Duplikate bei Wiederholungen.

Die Collection `pipeline_documents` wird initial angelegt, enthält im verifizierten Stand aber null Dokumente und wird vom Anwendungscode nicht beschrieben.

## Neo4j im Detail

Der ausgeführte Synchronisationspfad erzeugt ausschließlich `Machine` und `Component`. Pro Maschine entstehen vier direkte Komponenten. Pro Produktionslinie und Komponententyp referenzieren diese eine geteilte Utility-Komponente. Das ergibt 200 direkte plus 20 geteilte Komponenten, 50 Maschinen und jeweils 200 Beziehungen der Typen `HAS_COMPONENT` und `DEPENDS_ON`.

`cypher/schema.cypher` enthält zusätzlich Constraints und Beispiel-MERGE-Anweisungen für Factory und ProductionLine. `cypher/industrial_queries.cypher` enthält Abfragen für Pfade und Wartung. Compose oder DAG führen diese Dateien jedoch nicht automatisch aus. Deshalb gelten ihre zusätzlichen Labels nicht als live nachgewiesene Graphdaten.

## Spark-Unterrichtsinhalte

| Inhalt | Tatsächlicher Einsatz |
|---|---|
| `SparkSession` | Einstieg in `spark_jobs/transform.py` und `ml/train.py` |
| DataFrames | JSON-/CSV-Lesen, Auswahl, Filter, Spalten und Joins |
| Transformationen | `select`, `filter`, `withColumn`, `dropDuplicates`, `fillna`, `orderBy` |
| Actions | `count`, `collect`, Modell-Fit und Schreiboperationen |
| Spark SQL | temporäre View `machine_features` und Linienaggregation |
| Joins | Tageswerte mit Maschinen, Wartungen und Störungen |
| Window Functions | `lag`, rollende Werte, vergangene 7 Tage, `lead`, `dense_rank` |
| Aggregationen | `groupBy`, `avg`, `max`, `sum`, `count`, `stddev_pop` |
| Pivot | nicht implementiert |
| Parquet | Linienmetriken und nach Datum partitionierte Featuredaten |
| Feature Engineering | Tageswerte, Historienmittel, Änderungen, Abweichungen und Wochentag |

## Warum die Architektur industriell sinnvoll ist

Die Trennung schützt Verantwortlichkeiten: Rohdokumente bleiben vollständig, relationale Fakten erhalten Constraints, Graphbeziehungen bleiben abfragbar und große Featuretabellen liegen effizient in Parquet. Airflow macht den Batch nachvollziehbar und Spark hält Transformation und Modellierung in einem skalierbaren Rechenpfad. Für einen realen Betrieb fehlen jedoch Online-Ingestion, Security, Monitoring, Modellregistry und fachlich validierte Labels.
