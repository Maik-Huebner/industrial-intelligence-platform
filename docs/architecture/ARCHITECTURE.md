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
| Fabrik, Linien, Maschinen, Aufträge | PostgreSQL-orientierte CSV und PostgreSQL | Spark-Features; API liest PostgreSQL |
| rohe Sensormessungen | MongoDB `sensor_readings` | kontrollierter JSONL-Export, Quarantäne, Parquet |
| Wartungsexporte | CSV | PostgreSQL, Spark |
| Störungen | JSON | PostgreSQL normalisierte Events, Spark |
| Komponenten und Abhängigkeiten | Neo4j/Graph-Staging | parametrisierte Cypher-Abfragen der API |
| ML-Prognosen | PostgreSQL, erzeugt aus Spark-JSON | API liest die gewählte Modellversion; Historie bleibt versioniert |

IDs entstehen deterministisch. Upserts beziehungsweise `MERGE` machen Wiederholungen idempotent. Rohmessungen werden nicht in Neo4j dupliziert.

## Pipelinefolge

1. Quellen und Arbeitsverzeichnis prüfen.
2. Quellorientierte Dateien deterministisch erzeugen.
3. Der vollständige MongoDB-Load wird atomar aktiviert und kontrolliert exportiert.
4. Python normalisiert den Export und schreibt ungültige Zeilen in die Quarantäne.
5. Das Source Gate prüft Mengen, Identität, Maschinenabdeckung und Ausschussquote.
6. Spark transformiert den verifizierten Export und berechnet zeitliche Merkmale.
7. Das Feature Gate prüft Schema, Maschinen, Nullwerte, Klassen und Split-Grenzen.
8. MLlib trainiert und bewertet drei getrennte Aufgaben; Maschinenmetriken entstehen parallel.
9. Ergebnisse werden versioniert und idempotent nach PostgreSQL geschrieben.
10. Neo4j-Beziehungen werden per `MERGE` synchronisiert und über die API abgefragt.
11. Ein finaler Konsistenzcheck verifiziert Quellen und persistierte Endstände.
12. Der Lauf schreibt erst danach seinen kompakten Erfolgsbericht.

Große DataFrames werden auf dem gemeinsamen Datenvolume als Parquet transportiert, nie über XCom. FastAPI greift direkt auf PostgreSQL und Neo4j zu. MongoDB bleibt Sensorquelle für den Batch-Pfad und ist bewusst kein Online-Serving-Endpunkt.

## Sicherheits- und Betriebsgrenzen

Alle Secrets kommen aus `.env`; nur unverwendbare Beispielwerte werden versioniert. Veröffentlichte Ports binden standardmäßig an `127.0.0.1`. Das System setzt lokale Vertrauensgrenzen voraus, nutzt keine TLS-Terminierung und besitzt keine API-Authentifizierung oder rollenbasierte Autorisierung. Vor einem realen Betrieb sind Secret-Management, Netzwerksegmentierung, Verschlüsselung, Rate Limits, Backup-/Restore-Nachweise, Audit-Logging und ein freigegebener MLOps-Prozess erforderlich.
