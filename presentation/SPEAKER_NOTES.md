# Zehn-Minuten-Sprecherskript

Zielzeit: etwa 9:30 Minuten. Die Abschnitte entsprechen den zehn Folien der PowerPoint-Datei.

## Folie 1 – Projektvorstellung · 0:00–0:40

„Ich stelle die Industrial Intelligence Platform vor. Das Projekt verbindet Data Engineering, Big-Data-Verarbeitung und Predictive Maintenance in einer durchgängigen Anwendung. Die Plattform erzeugt reproduzierbare Fabrikdaten, führt sie aus vier Quellentypen zusammen, verarbeitet eine Million Sensormessungen mit Spark und macht Risiken über eine API zugänglich. Wichtig ist mir die Abgrenzung: Es ist ein technisch vollständiges Ausbildungs- und Portfolioprojekt auf synthetischen Daten, kein freigegebenes Wartungssystem.“

## Folie 2 – Industrielles Problem · 0:40–1:30

„In einem Werk liegen Informationen typischerweise verteilt: Stammdaten und Aufträge sind relational, Sensordaten dokumentenorientiert, Wartungen kommen aus CSV-Dateien, Störungen aus JSON und technische Abhängigkeiten bilden einen Graphen. Ohne gemeinsame Verarbeitung fehlt der Kontext für Wartungsprioritäten. Ein hoher Vibrationswert allein sagt wenig. Erst zusammen mit Maschinenalter, Last, Störungen, Wartungshistorie und betroffenen Komponenten entsteht eine nachvollziehbare Entscheidungsgrundlage.“

## Folie 3 – Ziele und Anforderungen · 1:30–2:20

„Die Lösung musste fünf Dinge gleichzeitig leisten: erstens reproduzierbare Daten bis eine Million Messungen, zweitens echte Nutzung von PostgreSQL, MongoDB und Neo4j, drittens einen orchestrierten ETL-Pfad über Airflow und Spark, viertens drei MLlib-Aufgaben und fünftens belastbare Tests und Dokumentation. Alle Schritte sind idempotent ausgelegt. Fehlerhafte Messungen werden nicht still gelöscht, sondern mit einem fachlichen Grund quarantänisiert.“

## Folie 4 – Systemarchitektur · 2:20–3:20

„Links sehen wir die Quellen: strukturierte Stammdaten, verschachtelte Sensoren, Wartungs-CSV, Störungs-JSON und Komponentenbeziehungen. Airflow steuert 13 Tasks. MongoDB ist die verifizierte Sensorquelle; ein kontrollierter Snapshot speist Spark. Zwei Quality Gates stoppen inkonsistente Quellen beziehungsweise Features vor ML und Persistenz. PostgreSQL speichert Resultate und Laufstatus, Neo4j hält den technischen Kontext, und FastAPI liest beide Systeme direkt. Messreihen werden bewusst nicht als Graphknoten modelliert.“

## Folie 5 – Datenhaltung · 3:20–4:10

„Die drei Datenbanksysteme sind keine Technologiedemonstration ohne Zweck. PostgreSQL sichert Stammdaten, Metriken, versionierte Prognosen und Pipeline-Läufe. MongoDB aktiviert nur vollständig geladene Sensor-Snapshots. Neo4j beantwortet Beziehungsfragen wie: Welche Komponenten hängen an einer kritischen Maschine und welche Nachbarmaschinen teilen eine Utility? Im Full-Lauf stehen 50 Metriken und 1.950 Prognosen in PostgreSQL, eine Million Sensordokumente in MongoDB sowie 270 Knoten und 400 Beziehungen in Neo4j.“

## Folie 6 – Airflow und ETL · 4:10–5:10

„Der DAG bildet den vollständigen Ablauf in 13 Tasks ab. Große Daten werden nicht über XCom verschoben. Der MongoDB-Snapshot wird gezählt, sortiert und atomar exportiert. Ein Source Gate liegt vor Spark, ein Feature Gate vor Metriken, ML und PostgreSQL-Persistenz. Im ausgeführten Full-DAG wurden 994.905 Messungen akzeptiert und 5.095 quarantänisiert. Das sind rund 0,51 Prozent. Alle 13 Tasks endeten erfolgreich.“

## Folie 7 – Apache Spark · 5:10–6:10

„Spark verarbeitet ausschließlich den verifizierten MongoDB-Export. Der Code nutzt DataFrames, Spark SQL, Joins und Window Functions. Die neuen Klassifikationsmerkmale enthalten Änderungen zum Vortag, Abweichungen vom vorherigen Sieben-Tage-Niveau und zyklische Wochentagswerte. Historische Fenster enden am Vortag. Das Label stammt aus dem Folgetag. Je ein Purge-Tag zwischen Training, Validierung und Test verhindert, dass dieser Target-Horizont eine Split-Grenze überschreitet. Aus einer Million Eingaben entstanden 994.905 gültige Messungen und 4.950 Tagesfeatures.“

## Folie 8 – Spark MLlib · 6:10–7:30

„Für die Klassifikation vergleiche ich eine Majority-Baseline, logistische Regression, Decision Tree, Random Forest und Gradient Boosted Trees. Parameter und Schwellenwerte stammen ausschließlich aus Training und Validierung. Das finale logistische Modell wird anschließend auf Training plus Validierung neu gefittet. Auf 950 unabhängigen Testzeilen steigt Macro-F1 von 0,432 auf 0,534 und Balanced Accuracy von 0,500 auf 0,537. Die Confusion-Matrix enthält 41 richtig negative, 187 falsch positive, 76 falsch negative und 646 richtig positive Fälle. Das Modell erkennt damit beide Klassen, aber der Recall für Klasse 0 von 0,180 bleibt schwach. Auch die Regression hat nun einen Purge-Tag: RMSE 0,514 Grad gegenüber 3,557 Grad der Baseline; KMeans erreicht 0,554 Silhouette.“

## Folie 9 – Ergebnisse und Live-Demo · 7:30–8:40

„In der Demo zeige ich zuerst den lokal gebundenen Stack und den API-Healthcheck gegen PostgreSQL. Danach rufe ich paginierte Prognosen mit der Modellversion `synthetic-v2-classification-benchmark`, die Pipeline-Laufhistorie und reale Neo4j-Abhängigkeiten ab. Die Vorhersagen enthalten beide Klassen. Zusätzlich bleiben der erfolgreiche 13-Task-Full-DAG, eine Million MongoDB-Dokumente und 400 Neo4j-Beziehungen als technische Evidenz erhalten. 32 automatisierte Tests bestanden.“

## Folie 10 – Fazit · 8:40–9:40

„Das Projekt erfüllt die lokale technische Zielsetzung: MongoDB ist die geprüfte Spark-Quelle, zwei Gates schützen Veröffentlichung, und FastAPI liest PostgreSQL und Neo4j direkt. Die Klassifikation verbessert sich messbar gegenüber der Majority-Baseline. Die Grenze bleibt Teil des Ergebnisses: 2.998 der 3.059 positiven Labels erfüllen den synthetischen Vibrationsgrenzwert. Vor einem Pilotbetrieb folgen echte Historien, fachlich validierte Labels, Authentifizierung, TLS, Rate Limits, Registry, Drift-Monitoring und Recovery-Übungen.“

## Zeitreserve · 9:40–10:00

Kurze Pause für Rückfrage oder Wechsel in die Live-Demo. Wenn die Demo bereits parallel erfolgt ist, endet der Vortrag hier nach ungefähr neun Minuten vierzig Sekunden.
