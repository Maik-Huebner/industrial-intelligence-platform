# Architektur und Datenfluss

## Entscheidungen

Die Plattform trennt Quellsysteme, kuratierte Daten und Analyseergebnisse. PostgreSQL ist die Quelle für stabile Unternehmensentitäten und Ziel für Kennzahlen. MongoDB nimmt variierende Sensordokumente mit Einheiten, Kontext und Lineage auf. Neo4j beantwortet Pfad- und Abhängigkeitsfragen. Dateien bilden typische externe Wartungs- und Störungsexporte ab.

Die lokale Referenzpipeline benötigt nur die Python-Standardbibliothek und beweist Generator, Validierung, Quarantäne, Aggregation und Ergebniszugriff. Die containerisierte Pipeline ersetzt diese Berechnungen nicht, sondern ergänzt die verteilte Spark-Verarbeitung und MLlib. So bleibt ein kleiner End-to-End-Lauf auch auf schwacher Hardware reproduzierbar.

## Source of Truth

| Entität | Führendes System | Replikate/Ziele |
|---|---|---|
| Fabrik, Linien, Maschinen, Aufträge | PostgreSQL | Spark-Features, API |
| rohe Sensormessungen | MongoDB/JSONL-Staging | validiertes CSV, Parquet |
| Wartungsexporte | CSV | PostgreSQL, Spark |
| Störungen | JSON | PostgreSQL normalisierte Events, Spark |
| Komponenten und Abhängigkeiten | Neo4j/Graph-Staging | API-Abfragen |
| ML-Prognosen | PostgreSQL | API, Report |

IDs entstehen deterministisch. Upserts beziehungsweise `MERGE` machen Wiederholungen idempotent. Rohmessungen werden nicht in Neo4j dupliziert.

## Pipelinefolge

1. Quellen und Arbeitsverzeichnis prüfen.
2. Quellorientierte Dateien deterministisch erzeugen.
3. Dokumente normalisieren und ungültige Zeilen quarantänisieren.
4. Spark transformiert Messreihen und berechnet zeitliche Merkmale.
5. Spark verbindet Stamm-, Wartungs- und Störungsdaten.
6. MLlib trainiert und bewertet drei getrennte Aufgaben.
7. Ergebnisse werden idempotent persistiert.
8. Neo4j-Beziehungen werden per `MERGE` synchronisiert.
9. Ein Qualitätsgate prüft die Ausschussquote.
10. Der Lauf schreibt einen kompakten Bericht.

Große DataFrames werden auf dem gemeinsamen Datenvolume als Parquet transportiert, nie über XCom.

## Sicherheits- und Betriebsgrenzen

Alle Secrets kommen aus `.env`; nur unverwendbare Beispielwerte werden versioniert. Das System setzt lokale Vertrauensgrenzen voraus, nutzt keine TLS-Terminierung und besitzt noch keine rollenbasierte API-Autorisierung. Vor einem realen Betrieb wären Secret-Management, Netzwerksegmentierung, Verschlüsselung, Backup, Audit-Logging und ein freigegebener MLOps-Prozess erforderlich.

