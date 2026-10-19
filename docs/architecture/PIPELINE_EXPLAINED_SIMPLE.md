# Die Pipeline einfach erklärt

Die Plattform simuliert eine Fabrik mit 50 Maschinen. Sie erzeugt Messwerte, Wartungen, Störungen und technische Komponenten. Jede Datenart landet dort, wo sie fachlich gut aufgehoben ist.

## Die drei Datenbanken

PostgreSQL schützt strukturierte Daten wie Maschinen, Wartungen und Modellprognosen. MongoDB bewahrt die verschachtelten Sensordokumente. Neo4j bildet ab, welche Maschinenkomponente von welcher geteilten technischen Versorgung abhängt.

Spark erhält seine Sensoren jetzt nachweislich aus MongoDB. Ein kleiner Python-Prozess liest die Collection in Batches, sortiert die Dokumente reproduzierbar und schreibt einen Snapshot mit Prüfsumme. Er lädt nie alle eine Million Dokumente gleichzeitig in den Arbeitsspeicher.

## Zwei Qualitätsampeln

Die erste Ampel prüft Rohdaten und den MongoDB-Export. Einzelne absichtlich fehlerhafte Messungen dürfen in Quarantäne. Fehlende Daten, doppelte IDs oder eine zu hohe Fehlerquote stoppen die Pipeline.

Spark berechnet danach Tageswerte und historische Merkmale. Die zweite Ampel prüft, ob alle 50 Maschinen vorhanden sind, beide Zielklassen vorkommen und Training, Validierung und Test zeitlich sauber getrennt sind. Erst dann trainiert MLlib.

## Ergebnisse und API

PostgreSQL bewahrt alte und neue Modellversionen gleichzeitig. Die API liefert standardmäßig nur die konfigurierte aktuelle Version. Eine historische Version muss ausdrücklich ausgewählt werden. Maschinen, Metriken, Prognosen und Läufe kommen direkt aus PostgreSQL. Ein eigener Endpunkt liest reale Komponentenabhängigkeiten aus Neo4j.

Die API besitzt keine Anmeldung. Docker veröffentlicht sie deshalb standardmäßig nur auf dem lokalen Rechner. Das genügt für ein Portfolio- und Lernsystem, aber nicht für einen öffentlichen Produktivbetrieb.

## Die wichtigsten Zahlen

- 1.000.000 Dokumente wurden vollständig aus MongoDB exportiert.
- 994.905 Messungen erfüllten den Qualitätsvertrag.
- 5.095 Messungen landeten nachvollziehbar in Quarantäne.
- Spark erzeugte 4.950 tägliche Featurezeilen.
- Die aktuelle Modellversion enthält 950 Testprognosen.
- Historische Prognosen bleiben erhalten.

Die Daten sind synthetisch. Die Plattform beweist technische Integration und reproduzierbare Evaluation, aber keine reale Wartungsleistung.
