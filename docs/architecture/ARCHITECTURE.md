# Architektur und Datenfluss

## Entscheidungen

Die Plattform trennt Quellsysteme, kuratierte Daten und Analyseergebnisse. PostgreSQL ist die Quelle für stabile Unternehmensentitäten und Ziel für Kennzahlen. MongoDB nimmt variierende Sensordokumente mit Einheiten, Kontext und Lineage auf. Neo4j beantwortet Pfad- und Abhängigkeitsfragen. Dateien bilden typische externe Wartungs- und Störungsexporte ab.

Die lokale Referenzpipeline benötigt nur die Python-Standardbibliothek und beweist Generator, Validierung, Quarantäne, Aggregation und Ergebniszugriff. Die containerisierte Pipeline ersetzt diese Berechnungen nicht, sondern ergänzt die verteilte Spark-Verarbeitung und MLlib. So bleibt ein kleiner End-to-End-Lauf auch auf schwacher Hardware reproduzierbar.

## Vertiefende Architekturdokumentation

- `END_TO_END_DATA_FLOW.md`: vollständiger technischer Datenfluss und Nachweise
- `SYSTEM_ARCHITECTURE.md`: Komponenten, Container, Mounts und Schnittstellen
- `TECHNOLOGY_RESPONSIBILITIES.md`: klare Technologieverantwortlichkeiten
- `DATA_LINEAGE.md`: Herkunft der Features und Vorhersagen
- `AIRFLOW_EXECUTION_FLOW.md`: exakter DAG-Ablauf
- `PIPELINE_DIAGRAM.md`: vollständiges Mermaid-Diagramm
- `PIPELINE_EXPLAINED_SIMPLE.md`: verständliche Erklärung für Gespräch und Präsentation

## Source of Truth

| Entität | Führendes System | Replikate/Ziele |
|---|---|---|
| Fabrik, Linien, Maschinen, Aufträge | PostgreSQL-orientierte CSV und PostgreSQL | Spark-Features; API liest die CSV |
| rohe Sensormessungen | MongoDB/JSONL-Staging | validiertes CSV, Parquet |
| Wartungsexporte | CSV | PostgreSQL, Spark |
| Störungen | JSON | PostgreSQL normalisierte Events, Spark |
| Komponenten und Abhängigkeiten | Neo4j/Graph-Staging | Cypher-Abfragen; aktuell kein API-Endpunkt |
| ML-Prognosen | Spark-JSON und PostgreSQL | API liest Spark-JSON; PostgreSQL archiviert versioniert |

IDs entstehen deterministisch. Upserts beziehungsweise `MERGE` machen Wiederholungen idempotent. Rohmessungen werden nicht in Neo4j dupliziert.

## Pipelinefolge

1. Quellen und Arbeitsverzeichnis prüfen.
2. Quellorientierte Dateien deterministisch erzeugen.
3. Dokumente normalisieren und ungültige Zeilen quarantänisieren.
4. Spark transformiert Messreihen und berechnet zeitliche Merkmale.
5. Spark verbindet Stamm-, Wartungs- und Störungsdaten.
6. MLlib trainiert und bewertet drei getrennte Aufgaben.
7. Ergebnisse werden idempotent persistiert.
8. Neo4j-Beziehungen werden per `MERGE` synchronisiert, bleiben aber außerhalb des ML- und API-Pfads.
9. Ein Qualitätsgate prüft die Ausschussquote.
10. Der Lauf schreibt einen kompakten Bericht.

Große DataFrames werden auf dem gemeinsamen Datenvolume als Parquet transportiert, nie über XCom. FastAPI greift im aktuellen Stand auf CSV- und JSON-Artefakte dieses Volumes zu und nicht direkt auf die drei Datenbanken.

## Sicherheits- und Betriebsgrenzen

Alle Secrets kommen aus `.env`; nur unverwendbare Beispielwerte werden versioniert. Das System setzt lokale Vertrauensgrenzen voraus, nutzt keine TLS-Terminierung und besitzt noch keine rollenbasierte API-Autorisierung. Vor einem realen Betrieb wären Secret-Management, Netzwerksegmentierung, Verschlüsselung, Backup, Audit-Logging und ein freigegebener MLOps-Prozess erforderlich.
