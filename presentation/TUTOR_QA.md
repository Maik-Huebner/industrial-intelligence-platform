# Zehn mögliche Tutorfragen mit Antworten

## 1. Warum drei Datenbanken?

Weil die Zugriffsmuster verschieden sind: PostgreSQL für konsistente strukturierte Fakten und Ergebnisse, MongoDB für hochvolumige verschachtelte Sensordokumente, Neo4j für mehrstufige technische Beziehungen. Dieselbe Information wird nicht wahllos verdreifacht.

## 2. Warum nicht alle Sensordaten in Neo4j?

Eine Million Messknoten würden Speicher und Traversierungen belasten, ohne die fachlichen Beziehungsfragen zu verbessern. Der Graph hält Anlagenstruktur; Zeitreihen bleiben in MongoDB und Parquet.

## 3. Wie ist Reproduzierbarkeit sichergestellt?

Fester Seed, deterministische IDs und Zeitverläufe, versionierte Abhängigkeiten sowie idempotente Upserts und `MERGE`. `small`, `medium` und `full` nutzen denselben Generatorpfad.

## 4. Wie verhindert die Pipeline Data Leakage?

Merkmale entstehen pro Maschine und Tag. Rückwärtsgerichtete Fenster enden am Vortag. Labels und Regressionsziel werden mit `lead` aus dem Folgetag gebildet. Der Klassifikationssplit ist chronologisch und lässt an beiden Grenzen je einen Tag aus, damit der eintägige Target-Horizont nicht über eine Grenze reicht.

## 5. Warum war 76 Prozent Accuracy hier schlecht?

Die frühere logistische Regression sagte alle 1.000 Testfälle positiv voraus. Bei 760 positiven Fällen entstanden 76 Prozent Accuracy ohne Trennschärfe. Das neue Modell erreicht geringere Accuracy von 0,723, verbessert aber Macro-F1 auf 0,534 und sagt beide Klassen voraus.

## 6. Warum wird `randomSplit` trotzdem verwendet?

Nur als explizites Unterrichtsbeispiel für Regression und Clustering. Die Klassifikationsauswahl nutzt einen purged chronologischen 60/20/20-Split. `randomSplit` beeinflusst weder Parameter noch Schwellenwert oder Modellwahl.

## 7. Was macht den Airflow-DAG robust?

Kleine XComs, Dateien und Datenbanken für große Payloads, Retries, Timeouts, maximal ein aktiver Lauf, idempotente Ladeoperationen und ein Quality Gate mit klarer Fehlergrenze.

## 8. Warum Spark bei nur einer Million Zeilen?

Eine Million Zeilen rechtfertigen Spark wirtschaftlich nicht automatisch. Hier demonstriert die Größe denselben verteilbaren Codepfad für DataFrames, SQL, Joins, Fenster, Aggregationen und Parquet. Die Grenze wird transparent dokumentiert.

## 9. Was bedeutet die KMeans-Silhouette 0,362?

Die Cluster sind nur mäßig getrennt. Ein kleiner Cluster von 85 Zeilen hat sehr hohe Anomalierate und Vibration; zwei große Cluster unterscheiden vor allem Last und Temperatur. Die Namen benötigen technische Validierung.

## 10. Was fehlt für Produktion?

Echte und governance-geprüfte Daten, fachlich validierte Labels, Kostenmatrix, Security und Rollen, Secrets-Management, Monitoring, SLA, Modellregistry, Drift-Erkennung, Rollback, Lasttests und ein kontrollierter Pilotbetrieb.
