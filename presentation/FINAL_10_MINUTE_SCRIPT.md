# Finales Zehn-Minuten-Sprecherskript

Zielzeit: **9:35 Minuten plus 25 Sekunden Reserve**.  
Umfang des gesprochenen Textes: rund 1.100 Wörter. Bei 115–120 Wörtern pro Minute ergibt das etwa 9:10–9:35 Minuten. Die Zeitangaben wurden für kurze Blickpausen und Folienwechsel auf insgesamt 9:35 Minuten geplant.

## Folie 1 – Industrial Intelligence Platform · 0:00–0:35

„Ich stelle heute die Industrial Intelligence Platform vor. Sie verbindet Data Engineering, Big-Data-Verarbeitung und Machine Learning in einem vollständigen Predictive-Maintenance-Beispiel. Die Plattform erzeugt reproduzierbare Fabrikdaten, integriert drei Datenbanksysteme, verarbeitet bis zu eine Million Sensormessungen mit Spark und stellt Ergebnisse über eine API bereit. Die wichtigste Abgrenzung gleich am Anfang: Das ist ein technisch validiertes Ausbildungs- und Portfolio-System auf synthetischen Daten, kein freigegebenes industrielles Wartungssystem.“

## Folie 2 – Problem und industrieller Kontext · 0:35–1:20

„In einem Werk liegen Informationen selten in einem einzigen System. Maschinenstammdaten und Aufträge sind relational. Sensoren liefern große, verschachtelte Zeitreihen. Wartungen kommen häufig als Tabellen, Störungen als JSON, und technische Abhängigkeiten bilden einen Graphen. Ein einzelner hoher Vibrationswert erklärt noch keinen Wartungsbedarf. Erst die Kombination aus Temperatur, Vibration, Last, Maschinenalter, Wartungshistorie und betroffenen Komponenten ergibt einen prüfbaren Kontext. Genau diese heterogenen Quellen führt die Plattform kontrolliert zusammen.“

## Folie 3 – Ziele und Qualitätskriterien · 1:20–2:05

„Die Lösung musste fünf Ziele gleichzeitig erfüllen: reproduzierbare Datenprofile bis eine Million Messungen; fachlich getrennte Aufgaben für PostgreSQL, MongoDB und Neo4j; eine orchestrierte ETL-Strecke mit Airflow und Spark; Klassifikation, Regression und Clustering in MLlib; und schließlich reale Tests und nachvollziehbare Dokumentation. Fehlerhafte Daten werden dabei niemals still verworfen. Sie landen mit Reason Code in Quarantäne. Wiederholte Läufe sind idempotent, Prognosen bleiben über eine Modellversion unterscheidbar, und ein unabhängiger Testsatz bleibt bis zur finalen Bewertung unangetastet.“

## Folie 4 – End-to-End-Architektur · 2:05–3:05

„Links erzeugt ein deterministischer Generator CSV-, JSON- und JSONL-Quellen. PostgreSQL speichert strukturierte Stamm-, Produktions-, Ergebnis- und Laufdaten. MongoDB ist die operative Quelle für die Sensordokumente. Neue Messungen werden erst in eine temporäre Collection geladen, geprüft und danach atomar aktiviert. Ein sortierter Snapshot dieses Bestands speist Spark. Neo4j hält Maschinen, Komponenten und ihre Abhängigkeiten. Airflow orchestriert 13 Tasks. Ein Source Gate liegt vor Spark, ein Feature Gate direkt vor ML und Ergebnis-Persistenz. FastAPI liest strukturierte Resultate direkt aus PostgreSQL und technische Abhängigkeiten direkt aus Neo4j. Es gibt also keinen Scheinpfad in der Architektur: Jede gezeigte Kernkomponente wird tatsächlich verwendet.“

## Folie 5 – Polyglotte Datenhaltung · 3:05–3:55

„Die drei Datenbanken wurden nach Zugriffsmuster gewählt. PostgreSQL erzwingt referenzielle Integrität und bedient die API für Maschinen, Tagesmetriken, Modellvorhersagen und Pipeline-Läufe. MongoDB nimmt eine Million verschachtelte Sensordokumente auf und stellt per Index und Snapshot einen stabilen Batch-Eingang bereit. Neo4j beantwortet Traversierungsfragen: Welche Komponenten hängen an einer Maschine, und welche weiteren Maschinen teilen technische Abhängigkeiten? Im Full-Lauf stehen 50 aktuelle Metriken und 1.950 historisch versionierte Prognosen in PostgreSQL, eine Million Sensordokumente in MongoDB sowie 50 Maschinen, 220 Komponenten und insgesamt 400 Beziehungen in Neo4j.“

## Folie 6 – Python ETL und Airflow · 3:55–4:55

„Der DAG bildet den gesamten Ablauf in 13 Tasks ab. Große Datenmengen laufen nicht durch XCom, sondern über Datenbanken und kontrollierte Dateien. Beim Full-Lauf wurden von einer Million Messungen 994.905 akzeptiert und 5.095 quarantänisiert. Die Ursachen sind vollständig erklärt: fehlende Temperatur, Werte außerhalb des erlaubten Temperaturbereichs und unbekannte Maschinen-IDs. Das Source Gate prüft Mengen, Eindeutigkeit, Referenzen und Fehlerquote. Das Feature Gate prüft später Schema, Nullschlüssel, Maschinenabdeckung, Klassen und Splitgrenzen. Der bekannte Full-DAG und zusätzlich zwei isolierte Fresh-Start-Läufe endeten jeweils mit 13 von 13 erfolgreichen Tasks. Der Clean-Start verwendete neue Volumes und verdeckte deshalb keinen Initialisierungsfehler durch alte Daten.“

## Folie 7 – Spark-Verarbeitung · 4:55–5:55

„Spark verarbeitet den verifizierten MongoDB-Snapshot mit DataFrames, Spark SQL, Inner und Left Joins, Aggregationen und Window Functions. `lag` bildet Änderungen zum Vortag, rückwärtsgerichtete Fenster berechnen das vorherige Sieben-Tage-Niveau, und `lead` erzeugt ausschließlich Zielwerte des Folgetags. Zukunftsspalten werden aus den Features ausgeschlossen. Aus dem Full-Datensatz entstehen 4.950 tägliche Featurezeilen. Für die Klassifikation trenne ich Training, Validierung und Test chronologisch im Verhältnis 60, 20 und 20 Prozent. Zwischen den Abschnitten liegt jeweils ein kompletter Purge-Tag, damit der eintägige Zielhorizont keine Grenze überschreitet. Im finalen Audit wurde derselbe Schutz auch für den 80/20-Regressionssplit ergänzt und automatisiert getestet.“

## Folie 8 – Spark MLlib · 5:55–7:25

„Für die Klassifikation vergleiche ich eine Majority-Baseline, logistische Regression, Decision Tree, Random Forest und Gradient Boosted Trees. Klassengewichte, Skalierung, Hyperparameter und Threshold werden ausschließlich mit Trainings- und Validierungsdaten bestimmt. Die Auswahlregel priorisiert Macro-F1 und anschließend Balanced Accuracy; beide Klassen müssen vorhergesagt werden. Die logistische Regression gewinnt mit Threshold 0,58 und wird danach auf Training plus Validierung neu trainiert. Im unabhängigen Test erreicht sie Accuracy 0,723, Macro-F1 0,534, Balanced Accuracy 0,537, PR-AUC 0,855 und ROC-AUC 0,632. Die Confusion Matrix enthält 41 richtig negative, 187 falsch positive, 76 falsch negative und 646 richtig positive Fälle. Die Majority-Baseline hat zwar 0,760 Accuracy, erkennt aber keinen einzigen negativen Fall und erreicht nur 0,432 Macro-F1. Die Verbesserung ist also real, aber klein: Der Recall für Klasse null beträgt nur 0,180. Die Regression erzielt RMSE 0,514 Grad gegenüber 3,557 Grad der Mittelwert-Baseline. KMeans erreicht Silhouette 0,554; die Cluster bleiben bewusst nummeriert, weil ihre Bedeutung nicht fachlich validiert wurde.“

## Folie 9 – Nachweis, API und Demo · 7:25–8:35

„In der kurzen Demo zeige ich zuerst den lokal gebundenen Docker-Stack und den Healthcheck. Danach rufe ich den letzten Pipeline-Lauf sowie eine Seite versionierter Prognosen aus PostgreSQL ab. Abschließend zeigt der Abhängigkeitsendpunkt echte Neo4j-Daten für eine Maschine. Alle Endpunkte wurden im Audit gegen den Datenbankinhalt geprüft. Insgesamt bestanden 32 automatisierte Tests mit aktivierten Containerintegrationen; zwei zusätzliche Spark-Vertragsprüfungen liefen im vorgesehenen Spark-3.5.3-Container. Die Präsentation selbst besitzt genau zehn Folien, wurde strukturell validiert und vollständig gerendert. Falls die Live-Demo ausfällt, dienen die versionierten JSON-Reports und der vorbereitete Demo-Ablauf als Fallback.“

## Folie 10 – Fazit und ehrliche Grenzen · 8:35–9:35

„Das Projekt erfüllt alle 13 verbindlichen Unterrichtsbereiche und ist als lokales Portfolio-Projekt reproduzierbar. MongoDB ist nachweisbar die Spark-Quelle, zwei Quality Gates schützen die ML-Strecke, PostgreSQL und Neo4j bedienen die API direkt, und das Modell trennt erstmals beide Klassen besser als die Majority-Baseline. Der Audit gibt den Quellcode deshalb für eine öffentliche Portfolio-Veröffentlichung frei. Er gibt aber keinen öffentlichen Betrieb frei. Vor Produktion fehlen echte und governance-geprüfte Daten, fachlich validierte Labels, Authentifizierung, Rollen, TLS, Rate Limits, ein Secret Store, nicht-root Container, Schwachstellenscans, Backups, Monitoring, Modellregistry und Drift-Erkennung. Die wichtigste Erkenntnis lautet daher: Ein gutes Engineering-Projekt zeigt nicht nur funktionierende Technik und Kennzahlen, sondern macht ebenso klar, was diese Kennzahlen noch nicht beweisen.“

## Reserve · 9:35–10:00

25 Sekunden für Folienwechsel, eine kurze Pause oder den Übergang zur Demo. Bei langsamerem Sprechen kann der zweite Satz von Folie 9 über die Präsentationsvalidierung entfallen, ohne eine Kernaussage zu verlieren.
