# Zehn-Minuten-Sprecherskript

Zielzeit: etwa 9:30 Minuten. Die Abschnitte entsprechen den zehn Folien der PowerPoint-Datei.

## Folie 1 – Projektvorstellung · 0:00–0:40

„Ich stelle die Industrial Intelligence Platform vor. Das Projekt verbindet Data Engineering, Big-Data-Verarbeitung und Predictive Maintenance in einer durchgängigen Anwendung. Die Plattform erzeugt reproduzierbare Fabrikdaten, führt sie aus vier Quellentypen zusammen, verarbeitet eine Million Sensormessungen mit Spark und macht Risiken über eine API zugänglich. Wichtig ist mir die Abgrenzung: Es ist ein technisch vollständiges Ausbildungs- und Portfolioprojekt auf synthetischen Daten, kein freigegebenes Wartungssystem.“

## Folie 2 – Industrielles Problem · 0:40–1:30

„In einem Werk liegen Informationen typischerweise verteilt: Stammdaten und Aufträge sind relational, Sensordaten dokumentenorientiert, Wartungen kommen aus CSV-Dateien, Störungen aus JSON und technische Abhängigkeiten bilden einen Graphen. Ohne gemeinsame Verarbeitung fehlt der Kontext für Wartungsprioritäten. Ein hoher Vibrationswert allein sagt wenig. Erst zusammen mit Maschinenalter, Last, Störungen, Wartungshistorie und betroffenen Komponenten entsteht eine nachvollziehbare Entscheidungsgrundlage.“

## Folie 3 – Ziele und Anforderungen · 1:30–2:20

„Die Lösung musste fünf Dinge gleichzeitig leisten: erstens reproduzierbare Daten bis eine Million Messungen, zweitens echte Nutzung von PostgreSQL, MongoDB und Neo4j, drittens einen orchestrierten ETL-Pfad über Airflow und Spark, viertens drei MLlib-Aufgaben und fünftens belastbare Tests und Dokumentation. Alle Schritte sind idempotent ausgelegt. Fehlerhafte Messungen werden nicht still gelöscht, sondern mit einem fachlichen Grund quarantänisiert.“

## Folie 4 – Systemarchitektur · 2:20–3:20

„Links sehen wir die Quellen: strukturierte Stammdaten, verschachtelte Sensoren, Wartungs-CSV, Störungs-JSON und Komponentenbeziehungen. Airflow steuert zehn fachliche Tasks. Die Qualitätsstufe trennt gültige von fehlerhaften Zeilen. Spark erzeugt Tagesmerkmale mit SQL, Joins, Fenstern und Aggregationen. MLlib trainiert Modelle, PostgreSQL speichert die Resultate, Neo4j hält den technischen Kontext und FastAPI stellt alles bereit. Messreihen werden bewusst nicht als Graphknoten modelliert, weil das den Graphen ohne Nutzen aufblähen würde.“

## Folie 5 – Datenhaltung · 3:20–4:10

„Die drei Datenbanksysteme sind keine Technologiedemonstration ohne Zweck. PostgreSQL sichert konsistente Stammdaten, Aufträge, Metriken und Prognosen. MongoDB passt zu den verschachtelten, variablen Sensordokumenten und zu Batch-Upserts. Neo4j beantwortet Beziehungsfragen wie: Welche Komponenten hängen an einer kritischen Maschine und welche Linie wäre betroffen? Im Full-Lauf stehen 50 Maschinen und 1.000 Prognosen in PostgreSQL, eine Million Sensordokumente in MongoDB sowie 270 Knoten und 400 Beziehungen in Neo4j.“

## Folie 6 – Airflow und ETL · 4:10–5:10

„Der DAG bildet den vollständigen Ablauf in zehn Tasks ab. Große Daten werden nicht über XCom verschoben; XCom enthält nur kleine Metadaten. Retries, Timeouts und ein Quality Gate sind konfiguriert. Im ausgeführten Full-DAG wurden 994.905 Messungen akzeptiert und 5.095 quarantänisiert. Das sind rund 0,51 Prozent und damit weniger als das erlaubte Gate von zwei Prozent. Der gesamte DagRun endete erfolgreich, einschließlich Spark, MLlib und Persistenz.“

## Folie 7 – Apache Spark · 5:10–6:10

„Spark verarbeitet den großen Messpfad. Der Code nutzt DataFrames, Spark SQL, Joins und Window Functions. Die neuen Klassifikationsmerkmale enthalten Änderungen zum Vortag, Abweichungen vom vorherigen Sieben-Tage-Niveau und zyklische Wochentagswerte. Historische Fenster enden am Vortag. Das Label stammt aus dem Folgetag. Je ein Purge-Tag zwischen Training, Validierung und Test verhindert, dass dieser Target-Horizont eine Split-Grenze überschreitet. Aus einer Million Eingaben entstanden 994.905 gültige Messungen und 4.950 Tagesfeatures.“

## Folie 8 – Spark MLlib · 6:10–7:30

„Für die Klassifikation vergleiche ich eine Majority-Baseline, logistische Regression, Decision Tree, Random Forest und Gradient Boosted Trees. Parameter und Schwellenwerte stammen ausschließlich aus Training und Validierung. Das finale logistische Modell wird anschließend auf Training plus Validierung neu gefittet. Auf 950 unabhängigen Testzeilen steigt Macro-F1 von 0,432 auf 0,534 und Balanced Accuracy von 0,500 auf 0,537. Die Confusion-Matrix enthält 41 richtig negative, 187 falsch positive, 76 falsch negative und 646 richtig positive Fälle. Das Modell erkennt damit beide Klassen, aber der Recall für Klasse 0 von 0,180 bleibt schwach. Regression und KMeans sind unverändert: RMSE 0,521 Grad gegenüber 3,536 Grad der Baseline und Silhouette 0,362.“

## Folie 9 – Ergebnisse und Live-Demo · 7:30–8:40

„In der Demo zeige ich zuerst den gesunden Stack und dann den API-Healthcheck. Danach rufe ich die 950 versionierten Testprognosen ab und öffne `classification_benchmark.json`. Die Vorhersagen enthalten beide Klassen und nennen die Modellversion `synthetic-v2-classification-benchmark`. Zusätzlich bleiben der erfolgreiche Full-DAG, eine Million MongoDB-Dokumente und 400 Neo4j-Beziehungen als technische Evidenz erhalten.“

## Folie 10 – Fazit · 8:40–9:40

„Das Projekt erfüllt die lokale technische Zielsetzung und verbessert die Klassifikation messbar gegenüber der Majority-Baseline. Die Grenze bleibt Teil des Ergebnisses: 2.998 der 3.059 positiven Labels erfüllen den synthetischen Vibrationsgrenzwert und Druckdaten existieren nicht. Als nächste Schritte würde ich deshalb echte Historien und fachlich validierte Labels anbinden. Eine separat versionierte Datenversion sollte Druck und plausible mehrtägige Verschleißtrajektorien ergänzen. Kosten falscher Alarme, Gerätesplit, Registry, Drift-Monitoring und Security folgen vor einem Pilotbetrieb.“

## Zeitreserve · 9:40–10:00

Kurze Pause für Rückfrage oder Wechsel in die Live-Demo. Wenn die Demo bereits parallel erfolgt ist, endet der Vortrag hier nach ungefähr neun Minuten vierzig Sekunden.
