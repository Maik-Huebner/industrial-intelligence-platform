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

„Spark verarbeitet den großen Messpfad. Der Code nutzt DataFrames zum Casten, Filtern und Deduplizieren. Eine temporäre View demonstriert Spark SQL. Joins verbinden Tageswerte mit Maschine, Wartung und Störung. Window Functions berechnen den vorherigen Messwert, einen rollenden Mittelwert, Rankings und – besonders wichtig – Ziele aus dem Folgetag. So wird zukünftige Information nicht als Merkmal des aktuellen Tages verwendet. Aus einer Million Eingaben entstanden 994.905 gültige Messungen und 4.950 Tagesfeatures.“

## Folie 8 – Spark MLlib · 6:10–7:30

„Für die Klassifikation vergleiche ich logistische Regression und Entscheidungsbaum. Für die Temperaturprognose nutze ich lineare Regression, für Maschinenzustände KMeans mit drei Clustern. Alle Modelle sind Pipelines mit Indexierung, Feature-Assembly und – wo sinnvoll – Skalierung. Die Validierung ist chronologisch: 3.950 Trainings- und 1.000 Testzeilen. Die Regression erreicht 0,521 Grad RMSE gegenüber 3,536 Grad der Baseline. Das Clustering hat eine Silhouette von 0,362. Die Klassifikations-Accuracy von 0,760 darf man dagegen nicht schönreden: Die logistische Regression sagt alle Testfälle positiv voraus. Die Confusion-Matrix zeigt damit fehlende Trennschärfe. Genau diese ehrliche Interpretation gehört für mich zu guter ML-Arbeit.“

## Folie 9 – Ergebnisse und Live-Demo · 7:30–8:40

„In der Demo zeige ich zuerst den gesunden Stack und dann den API-Healthcheck. Danach rufe ich Prognosen ab und öffne den gespeicherten Airflow-Report. Der Full-Lauf hat eine Million MongoDB-Dokumente, 1.000 PostgreSQL-Prognosen und 400 Neo4j-Beziehungen nachgewiesen. Zusätzlich zeigt der transparente lokale Baseline-Score Maschine M-017 als höchste Wartungspriorität. Dieser Score ist bewusst getrennt vom MLlib-Modell und erklärt seine Faktoren offen.“

## Folie 10 – Fazit · 8:40–9:40

„Das Projekt erfüllt die lokale technische Zielsetzung: Polyglot Persistence, Datenqualität, Airflow, Spark, MLlib, API, Tests und Dokumentation arbeiten zusammen. Die wichtigste Erkenntnis ist, dass eine funktionierende Pipeline nicht automatisch ein gutes Modell bedeutet. Als nächste Schritte würde ich echte Historien und fachlich validierte Labels anbinden, Kosten falscher Alarme berücksichtigen und Modellregistry, Drift-Monitoring, Security und Streaming ergänzen. Die öffentliche GitHub-Veröffentlichung habe ich bewusst nicht erzwungen: Die vorhandene CLI-Anmeldung war ungültig, deshalb wartet nur dieser letzte externe Schritt auf eine verifizierte Identität.“

## Zeitreserve · 9:40–10:00

Kurze Pause für Rückfrage oder Wechsel in die Live-Demo. Wenn die Demo bereits parallel erfolgt ist, endet der Vortrag hier nach ungefähr neun Minuten vierzig Sekunden.

