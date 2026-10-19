# Technologieverantwortlichkeiten

| Technologie | Verantwortung | Bewusste Grenze |
|---|---|---|
| Python | Generator, Streaming-Validierung, Quarantäne, MongoDB-Export, CLI und Adapter | keine verteilte Berechnung der Featurehistorie |
| MongoDB | aktive verschachtelte Rohsensorquelle und Snapshot-Audit in `pipeline_documents` | keine ML-Ergebnisse, keine unkontrollierte zweite Wahrheit |
| Apache Spark | validierte Sensorverarbeitung, Joins, SQL, Windows, Tagesaggregation und Parquet | keine Datenquelle und kein Orchestrator |
| Spark MLlib | Klassifikation, Regression und Clustering | kein Online-Scoring und keine Modellregistry |
| PostgreSQL | relationale Fakten, Tagesmetriken, versionierte Prognosen und Pipeline-Läufe | keine Million Rohsensordokumente |
| Neo4j | Maschinen-Komponenten-Abhängigkeiten und geteilte Utilities | keine Sensorzeitreihe und keine behaupteten Kausalwirkungen |
| Apache Airflow | Abhängigkeiten, Retries, Timeouts, Quality Gates und Laufstatus | keine Massendaten in XCom |
| FastAPI | begrenzter Read-Zugriff auf PostgreSQL und Neo4j | keine Authentifizierung und kein öffentlich sicherer Betrieb |
| Docker Compose | reproduzierbare lokale Services, Netzwerk, Volumes und Healthchecks | kein Produktionsorchestrator |
| Parquet | partitionierter analytischer Featurebestand | kein transaktionales Serving-System |

## Warum kontrollierter Export statt MongoDB-Spark-Connector

Der direkte Connector würde zusätzliche Maven/JAR-Versionen in Driver und Worker einführen. Der vorhandene Stack besitzt dagegen bereits einen getesteten PyMongo-Adapter und ein gemeinsames Volume. Der kontrollierte Export hält MongoDB als Quelle nachweisbar, verarbeitet den Cursor batchweise, sortiert reproduzierbar nach `reading_id` und erzeugt ein Zählungs- und Hash-Manifest. Dieser Pfad ist für das lokale Portfolio-System stabiler und leichter automatisiert zu testen.

## PostgreSQL als Serving-Schicht

FastAPI verwendet parameterisierte SQL-Abfragen mit Verbindungs- und Statement-Timeouts. Maschinen und Tagesmetriken werden deterministisch sortiert. Prognosen verwenden die eindeutige Kombination aus Maschine, Datum, Modellname und Modellversion. Ohne Query-Parameter liefert die API nur `IIP_CURRENT_MODEL_VERSION`; historische Versionen bleiben per expliziter Auswahl erreichbar. Pagination ist begrenzt und meldet Gesamtzahl, Limit und Offset in Response-Headern.

## MongoDB und `pipeline_documents`

`sensor_readings` enthält ausschließlich den letzten vollständig veröffentlichten Snapshot. Der Loader schreibt zuerst in eine temporäre Collection mit Unique Index. `pipeline_documents` speichert Datensatzanzahl, Batchgröße, SHA-256 und Zeitpunkte des aktiven Snapshots. Damit kann ein Lauf seine MongoDB-Quelle nachvollziehbar belegen.

## Neo4j im Serving-Pfad

`GET /machines/{machine_id}/dependencies` liefert direkte Komponenten, deren `DEPENDS_ON`-Utility und Maschinen, die dieselbe Utility referenzieren. Die Cypher-Abfrage bindet `machine_id` und `limit` als Parameter. Das API-Limit beträgt 200 Zeilen; je Abhängigkeit werden höchstens 25 Nachbarmaschinen geliefert.

## Validierungsvertrag

Python und Spark teilen Pflichtfelder und folgende inklusive Wertebereiche:

| Merkmal | Minimum | Maximum |
|---|---:|---:|
| Temperatur | -40 °C | 180 °C |
| Vibration | 0 mm/s | 50 mm/s |
| Leistung | 0 kW | 500 kW |
| Last | 0 % | 100 % |

Python erzeugt Reason Codes und Quarantäne. Spark setzt dieselbe fachliche Semantik mit DataFrame-Ausdrücken um. Ein Spark-Testfall prüft gemeinsame Grenzwerte. Das Source-Gate erlaubt eine erwartete Ausschussquote bis zwei Prozent; Identitäts-, Referenz- oder Vollständigkeitsfehler bleiben kritisch.
