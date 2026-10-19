# Die Pipeline einfach erklärt

## Kurzfassung für ein Vorstellungsgespräch

Die Plattform simuliert eine Fabrik mit 50 Maschinen. Ein Python-Generator erzeugt Maschinen, Aufträge, Wartungen, Störungen, Komponenten und eine Million Sensormessungen. Die Rohdaten werden passend zu ihrer Form gespeichert: relationale Fakten in PostgreSQL, verschachtelte Sensordokumente in MongoDB und technische Abhängigkeiten in Neo4j.

Airflow steuert den Batch. Zuerst erzeugt und lädt die Pipeline die Quellen. Danach prüft Python jede Sensormessung. 994.905 Messungen sind gültig, 5.095 landen mit Fehlergrund in der Quarantäne. Spark liest die Rohsensoren und verbindet sie mit Maschinen-, Wartungs- und Störungsdaten. Daraus entstehen 4.950 Tageszeilen mit Merkmalen pro Maschine.

MLlib nutzt diese Features für drei Aufgaben: Klassifikation eines Risikos am Folgetag, Temperaturregression und Clustering von Betriebszuständen. Für die Klassifikation gibt es getrennte Zeiträume für Training, Validierung und Test. Das finale logistische Modell sagt beide Klassen voraus und verbessert Macro-F1 und Balanced Accuracy gegenüber der Majority-Baseline. Die Trennung ist trotzdem schwach und wegen synthetischer Daten nicht produktionsreif.

Die Resultate werden als Dateien gespeichert und zusätzlich nach PostgreSQL geladen. FastAPI liefert die Dateien als REST-Antwort aus. Neo4j beantwortet Beziehungsfragen, beeinflusst das Modell aber aktuell nicht.

## Was die drei Datenbanken machen

### PostgreSQL

PostgreSQL ist das geordnete Register. Dort liegen Maschinen, Aufträge, Wartungen, Störungen, Tagesmetriken und versionierte Modellvorhersagen. Foreign Keys und Constraints schützen die Konsistenz.

### MongoDB

MongoDB ist das vollständige Sensorarchiv. Ein Dokument enthält mehrere verschachtelte Sensorwerte, Einheiten, den Betriebskontext und Lineage. Bei einer Million Dokumenten vermeiden Batch-Upserts langsame Einzeloperationen und doppelte `reading_id`-Werte.

### Neo4j

Neo4j ist der technische Lageplan. Es zeigt, welche Maschine welche Komponenten besitzt und welche Komponenten von einer gemeinsamen Utility abhängen. So lassen sich betroffene Maschinen oder kurze Abhängigkeitspfade abfragen. Der Graph liefert derzeit keine ML-Features.

## Was Airflow macht

Airflow ist der Ablaufplaner. Es hält keine Million Messungen in XCom, sondern startet zehn Tasks in der richtigen Reihenfolge und speichert nur kleine Statuswerte. Airflow protokolliert Fehler, wiederholt fehlgeschlagene Tasks und zeigt den letzten Lauf an.

## Was Spark macht

Spark ist die Rechenmaschine für die große Tabelle. Es liest JSONL und CSV, filtert ungültige Werte, entfernt Duplikate, aggregiert pro Tag und Maschine und verbindet mehrere Quellen. Window Functions berechnen vorherige Werte, historische Mittel und Folgetag-Ziele. Parquet speichert die Featuredaten spaltenorientiert und nach Datum partitioniert.

## Was MLlib macht

MLlib trainiert Modelle direkt auf den Spark-Features. Die Klassifikation vergleicht eine Majority-Baseline, logistische Regression, Decision Tree, Random Forest und Gradient Boosted Trees. Nur Training und Validierung bestimmen Hyperparameter und Threshold. Der Test bleibt für die abschließende Bewertung getrennt.

Das finale Modell erreicht auf 950 Testzeilen Macro-F1 0,534 und Balanced Accuracy 0,537. Es erkennt 41 negative und 646 positive Fälle korrekt. Weil es aber nur 17,98 Prozent der negativen Fälle erkennt, darf man keine Produktionsreife behaupten.

## Vier Zahlen, die man erklären können sollte

- **1.000.000:** erzeugte und in MongoDB gespeicherte Sensordokumente.
- **994.905:** gültige Messungen nach Qualitätsprüfung; 5.095 wurden bewusst nicht still verworfen, sondern quarantänisiert.
- **4.950:** 99 Featuretage für jeweils 50 Maschinen. Der letzte Tag entfällt wegen des Folgetag-Targets.
- **950:** unabhängige Testvorhersagen der neuen Klassifikationsversion.

## Ehrliche Architekturgrenzen

Im aktuellen Stand liest Spark nicht direkt aus MongoDB, sondern aus derselben JSONL-Stagingdatei, die auch nach MongoDB geladen wird. FastAPI liest ebenfalls Dateien und nicht PostgreSQL. Neo4j liefert Kontext, aber keine Features. Diese Punkte sind keine versteckten Behauptungen, sondern klar dokumentierte Ausbaugrenzen.

## Gute Antwort auf „Warum ist die Architektur sinnvoll?“

Die Datenform bestimmt das System: PostgreSQL schützt strukturierte Fakten, MongoDB bewahrt verschachtelte Rohsensoren, Neo4j modelliert Beziehungen, Spark verarbeitet die großen Tabellen und Airflow macht den Batch wiederholbar. Die Trennung erleichtert Tests und spätere Erweiterungen. Für eine Produktionseinführung müssten die Dateischnittstellen, Security, Monitoring und Modellverwaltung weiterentwickelt werden.
