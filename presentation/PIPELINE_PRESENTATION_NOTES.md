# Präsentationsnotizen zur End-to-End-Pipeline

## Erklärung in ungefähr zwei Minuten

Die Industrial Intelligence Platform bildet eine vollständige Batch-Pipeline für Predictive Maintenance ab. Ausgangspunkt ist ein deterministischer Python-Generator. Er erzeugt 50 Maschinen, 600 Produktionsaufträge, Wartungen und Störungen sowie eine Million verschachtelte Sensordokumente.

Die Daten werden nach ihrer Struktur aufgeteilt. PostgreSQL speichert konsistente Stamm- und Ereignisdaten sowie Tagesmetriken und versionierte Modellvorhersagen. MongoDB bewahrt die vollständigen Sensordokumente mit Einheiten, Kontext und Lineage. Neo4j modelliert Maschinen, Komponenten und gemeinsame technische Abhängigkeiten. Neo4j liegt bewusst außerhalb des ML-Pfads.

Airflow orchestriert zehn Tasks. Die Python-Qualitätsprüfung akzeptiert 994.905 Messungen und schreibt 5.095 fehlerhafte Datensätze mit Begründung in die Quarantäne. Spark liest die rohe Sensor-JSONL, filtert und dedupliziert sie, aggregiert pro Maschine und Tag und verbindet Maschinen-, Wartungs- und Störungsdaten. Historische Window Features verwenden nur vergangene Tage. Das Folgetag-Label wird mit `lead(1)` gebildet.

MLlib vergleicht fünf Klassifikatoren und trainiert zusätzlich eine Temperaturregression sowie KMeans. Die Klassifikation trennt Training, Validierung und Test chronologisch und lässt an den Grenzen je einen Tag aus. Das finale logistische Modell erreicht Macro-F1 0,534 und Balanced Accuracy 0,537. Es sagt beide Klassen voraus, erkennt aber nur 17,98 Prozent der negativen Fälle. Deshalb ist das Ergebnis eine nachgewiesene Verbesserung gegenüber der Majority-Baseline, aber keine Produktionsfreigabe.

Die neue Modellversion erzeugt 950 Testvorhersagen. Airflow lädt diese zusätzlich nach PostgreSQL. FastAPI liefert aktuell die JSON- und CSV-Artefakte vom gemeinsamen Volume aus. Dieser dateibasierte Serving-Pfad ist funktional, aber eine spätere Datenbank- oder Online-Inference-Anbindung bleibt ein Ausbaupunkt.

## Die drei Datenbanksysteme

### PostgreSQL

PostgreSQL hält strukturierte Fakten mit Primärschlüsseln, Foreign Keys und Checks. Dazu gehören Maschinen, Aufträge, Wartungen, Störungen, Tagesmetriken und ML-Vorhersagen. Modellname und Modellversion sind Teil des fachlichen Eindeutigkeitsschlüssels. Aktuell liegen 1.000 ältere und 950 neue Vorhersagen parallel vor.

### MongoDB

MongoDB speichert eine Million verschachtelte Sensordokumente. Jedes Dokument enthält mehrere Messwerte, Einheiten, Betriebskontext und Lineage. Ein Unique Index auf `reading_id` und Upserts verhindern Duplikate. Spark liest aktuell die JSONL-Stagingdatei und nicht direkt die Collection.

### Neo4j

Neo4j hält 50 Maschinen und 220 Komponenten. 200 `HAS_COMPONENT`- und 200 `DEPENDS_ON`-Beziehungen bilden direkte und geteilte Abhängigkeiten. Der Graph beantwortet Kontext- und Pfadfragen, ist aber nicht in die Modellfeatures oder die aktuelle API integriert.

## Airflow

Airflow plant den DAG täglich um 02:00 Uhr und begrenzt ihn auf einen aktiven Lauf. Zwei Retries, Timeouts und Tasklogs sichern die Ausführung ab. Große Daten bleiben auf Volumes. XCom transportiert nur kleine Metadaten. Der letzte Full-Lauf endete erfolgreich. Das Qualitätsgate liegt aktuell nach der Persistenz; diese Reihenfolge ist dokumentiert und sollte bei einer Produktionshärtung geändert werden.

## Spark

Spark verwendet DataFrames, Transformationen, Actions, SQL, Joins, Window Functions und Aggregationen. Die Featuredaten werden als Parquet nach Datum partitioniert. Driver und Worker sehen `data`, `reports` und `models` unter identischen Pfaden. Dadurch funktioniert der Dateizugriff im Standalone-Cluster konsistent.

## MLlib

Die Klassifikation verwendet One-Hot-Encoding für den Maschinentyp, einen VectorAssembler und StandardScaler für die logistische Regression. Während des Tunings stammen die Klassen­gewichte nur aus dem Training. Beim finalen Refit werden sie auf Training plus Validierung neu berechnet. Threshold und Hyperparameter stammen aus Training und Validierung. Regression und KMeans bleiben als getrennte Aufgaben erhalten. Eine Modellregistry oder Online-Inference ist nicht implementiert.

## Warum die Architektur industriell sinnvoll ist

Die Architektur trennt unveränderte Rohdaten, relationale Fakten, technische Beziehungen und analytische Features. So kann jedes System seine Stärke ausspielen. Airflow sorgt für Wiederholbarkeit und Spark für einen skalierbaren Rechenpfad. Die Lösung zeigt eine realistische Integrationsstruktur, ohne die synthetischen Daten oder das schwache Klassifikationsergebnis als Produktionsnachweis zu überhöhen.

## Zehn typische technische Rückfragen

### 1. Warum drei Datenbanken?

Weil die Datenformen verschieden sind. PostgreSQL schützt strukturierte Fakten, MongoDB speichert verschachtelte Rohsensoren und Neo4j beantwortet Beziehungs- und Pfadfragen.

### 2. Liest Spark direkt aus MongoDB?

Nein. Der aktuelle Spark-Job liest die JSONL-Stagingdatei. Dieselbe Datei wird zusätzlich vollständig nach MongoDB geladen. Ein Spark-Mongo-Connector ist nicht implementiert.

### 3. Liest FastAPI die PostgreSQL-Vorhersagen?

Nein. FastAPI liest aktuell `ml_predictions_json` vom gemeinsamen Volume. PostgreSQL speichert dieselben Vorhersagen zusätzlich versioniert.

### 4. Warum werden aus einer Million Messungen nur 994.905 gültige Zeilen?

Der Generator injiziert Qualitätsfehler. 1.757 Zeilen haben keine Temperatur, 1.693 verletzen den Temperaturbereich und 1.645 referenzieren eine unbekannte Maschine. Sie werden quarantänisiert.

### 5. Warum gibt es 4.950 Featurezeilen?

Es gibt 50 Maschinen und 100 Kalendertage. Für das Folgetag-Target entfällt der letzte Tag jeder Maschine. Somit bleiben 50 mal 99 gleich 4.950 Zeilen.

### 6. Wie wird Data Leakage verhindert?

Historische Fenster enden am Vortag. `future_*`-Spalten und `risk_rank` sind keine Klassifikationsfeatures. Zwischen Training, Validierung und Test liegt jeweils ein Purge-Tag.

### 7. Warum ist Accuracy nicht die wichtigste Kennzahl?

Die Testmenge enthält 76 Prozent positive Fälle. Eine reine Positive-Vorhersage erreicht bereits 0,760 Accuracy, erkennt aber keinen negativen Fall. Deshalb werden Macro-F1 und Balanced Accuracy priorisiert.

### 8. Ist das Modell produktionsreif?

Nein. Balanced Accuracy 0,537 und Recall 0,180 für Klasse 0 zeigen nur schwache Trennung. Außerdem stammen Daten und Labels vollständig aus einer Simulation.

### 9. Welche Rolle spielt Neo4j für die Vorhersage?

Aktuell keine direkte. Neo4j liefert technischen Kontext für Abhängigkeitsanalysen. Diese Trennung wird offen dargestellt.

### 10. Was wäre der wichtigste nächste Architektur-Schritt?

Die Qualitätsprüfung sollte vor der Veröffentlichung liegen. Danach wären direkte, klar versionierte Serving-Quellen, Authentifizierung, Monitoring, Modellregistry und reale Datenprioritäten sinnvoll.
