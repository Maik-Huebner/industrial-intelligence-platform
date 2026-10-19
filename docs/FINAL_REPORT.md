# Abschlussbericht

**Projekt:** Industrial Intelligence Platform  
**Abnahmedatum:** 19. Oktober 2026  
**Status:** Technische Lösung lokal abgeschlossen und getestet; öffentliche GitHub-Veröffentlichung blockiert, weil die GitHub-CLI keine gültige Anmeldung besitzt.

## 1. Implementierungsstatus

Die Plattform ist als integrierte End-to-End-Anwendung umgesetzt. Sie erzeugt deterministische Industriedaten, verteilt diese fachlich auf PostgreSQL, MongoDB, Dateien und Neo4j, validiert und quarantänisiert fehlerhafte Messungen, berechnet Spark-Merkmale, trainiert drei MLlib-Aufgabentypen und stellt Resultate per API bereit. Docker Compose und Airflow verbinden die Komponenten.

| Bereich | Implementiert | Tatsächlich getestet | Ergebnis |
|---|:---:|:---:|---|
| Reproduzierbarer Generator | ja | ja | Full-Profil: 1.000.000 Messungen |
| PostgreSQL | ja | ja | gesund; 50 Maschinen, 950 neue und 1.000 erhaltene ML-Prognosen |
| MongoDB | ja | ja | gesund; 1.000.000 Sensordokumente |
| Neo4j | ja | ja | gesund; 270 Knoten, 400 Beziehungen |
| Python-ETL und Datenqualität | ja | ja | 994.905 valide, 5.095 Quarantänefälle |
| Airflow-DAG | ja | ja | Import fehlerfrei; Full-DAG erfolgreich |
| Spark DataFrames/SQL/Joins/Windows/Aggregationen | ja | ja | 4.950 Feature-Zeilen |
| MLlib Klassifikation/Regression/KMeans | ja | ja | echte Kennzahlen gespeichert |
| FastAPI | ja | ja | Container gesund; Prognose-Endpunkt abgefragt |
| Tests | ja | ja | 17 schnelle + 4 Containerintegrationstests bestanden |
| Präsentation und Begleitmaterial | ja | ja | zehn Folien, visuell geprüft |
| GitHub-Veröffentlichung | vorbereitet | nein | wegen ungültiger `gh`-Authentifizierung ausgesetzt |

## 2. Tatsächlich ausgeführte Services

Die folgende Kombination lief gleichzeitig in Docker Compose: PostgreSQL 16.4, MongoDB 7.0.14, Neo4j 5.23, Spark 3.5.3 Master/Worker, Airflow 2.10.2 Webserver/Scheduler und die FastAPI. Wegen bereits belegter Standardports wurden für den Abnahmelauf ausschließlich Host-Ports geändert: PostgreSQL 65432, MongoDB 57017, Neo4j 57474/57687, API 58000 und Airflow 58080. Die internen Compose-Ports blieben unverändert.

`docker compose ps` meldete API, Airflow-Webserver, PostgreSQL, MongoDB, Neo4j und Spark Master als gesund; Scheduler und Worker liefen. `GET /health` lieferte `{"status":"ok","pipeline_artifacts_available":true}`.

## 3. Datenbankintegration

- PostgreSQL: 50 Maschinen, 600 Produktionsaufträge, 320 Wartungen, 180 normalisierte Störungsereignisse, 50 Tagesmetriken und 1.950 versionierte ML-Prognosen. Davon gehören 950 zur neuen Benchmark-Version; die 1.000 vorherigen Resultate bleiben erhalten. Upserts verwenden Primärschlüssel und `ON CONFLICT`.
- MongoDB: 1.000.000 verschachtelte Sensordokumente. Eindeutiger `reading_id`-Index und Batch-Upserts sichern Wiederholbarkeit.
- Neo4j: 270 Knoten und 400 gerichtete Beziehungen. Constraints und `MERGE` verhindern Duplikate; der Graph enthält bewusst technische Beziehungen statt eine Million Messknoten.

## 4. Datenmengen und ETL-Ergebnis

Der Full-Generator erzeugte bei Seed `20261019`:

| Entität | Anzahl |
|---|---:|
| Sensormessungen | 1.000.000 |
| Maschinen | 50 |
| Produktionslinien | 5 |
| Produktionsaufträge | 600 |
| Wartungen | 320 |
| Störungen | 180 |

Die Qualitätsprüfung akzeptierte 994.905 Messungen und stellte 5.095 Datensätze unter Quarantäne: 1.757 fehlende Temperaturen, 1.693 Temperatur-Bereichsverletzungen und 1.645 unbekannte Maschinenreferenzen. Die Ausschussquote von rund 0,51 Prozent lag unter dem Airflow-Gate von zwei Prozent. Es wurden keine Duplikate gefunden.

## 5. Airflow-DAG

`industrial_etl` enthält exakt die zehn geforderten fachlichen Schritte: Quellen validieren, Daten extrahieren, normalisieren, Spark ausführen, Maschinenmetriken berechnen, MLlib ausführen, PostgreSQL persistieren, Neo4j synchronisieren, Qualitäts-Gate prüfen und Zusammenfassung schreiben. Retry, Timeout, ein aktiver Lauf und kleine XCom-Payloads sind konfiguriert.

Am 19. Oktober 2026 wurde `airflow dags test industrial_etl 2026-10-19` mit `IIP_PROFILE=full` ausgeführt. Der DagRun endete mit `state=success`. Die Zusammenfassung meldet `postgres_rows=1000` (50 Tagesmetriken plus 950 neue Testprognosen), `neo4j_rows=200` und ein bestandenes Qualitäts-Gate. Der Wert 200 bezeichnet synchronisierte Komponenten-Zeilen; daraus entstehen zwei Beziehungstypen und insgesamt 400 Graphbeziehungen.

## 6. Spark-Transformation

Der Spark-Lauf las 1.000.000 JSONL-Messungen, normalisierte Typen und Zeitstempel, filterte ungültige Werte und entfernte Duplikate. DataFrame-Operationen, Spark SQL, mehrere Joins, `lag`, rollender Mittelwert, `lead`, Ranking und Aggregationen sind im selben Feature-Engineering-Pfad integriert. Ergebnis: 994.905 valide Messungen und 4.950 tagesbezogene Feature-Zeilen für 50 Maschinen. Die Ausgabe liegt partitioniert als Parquet vor.

Das Ziel für Klassifikation und Regression wird ausschließlich aus dem Folgetag gebildet. Die neuen Klassifikationsmerkmale verwenden zusätzlich rückwärtsgerichtete 7-Tage-Fenster, Tagesänderungen, Abweichungen vom historischen Niveau und zyklische Wochentagsmerkmale. Die Fenster enden am Vortag. Zukünftige Outcomes, `risk_rank` und alle `future_*`-Spalten sind als Klassifikationsmerkmale ausgeschlossen.

## 7. MLlib-Modelle und echte Kennzahlen

Die Klassifikation verwendet einen purged chronologischen 60/20/20-Split: 2.950 Trainings-, 950 Validierungs- und 950 Testzeilen; der 8. und 28. September sind wegen des eintägigen Label-Horizonts ausgelassen. Parameter, Klassengewichte und Schwellenwerte stammen ausschließlich aus Training und Validierung. Der Test wurde nicht für die Auswahl verwendet. Regression und KMeans behalten den bisherigen 80/20-Pfad unverändert.

| Aufgabe | Modell | Kennzahl | Ergebnis |
|---|---|---|---:|
| Klassifikation | Majority-Baseline | Accuracy / Macro-F1 / Balanced Accuracy | 0,760 / 0,432 / 0,500 |
| Klassifikation | Finale logistische Regression | Accuracy / Macro-F1 / Balanced Accuracy | 0,723 / 0,534 / 0,537 |
| Klassifikation | Finale logistische Regression | PR-AUC / ROC-AUC | 0,855 / 0,632 |
| Regression | Lineare Regression | RMSE | 0,521 °C |
| Regression | Lineare Regression | MAE | 0,443 °C |
| Regression | Mittelwert-Baseline | RMSE | 3,536 °C |
| Clustering | KMeans, k=3 | Silhouette | 0,362 |

### Ehrliche Interpretation

Die frühere logistische Regression klassifizierte alle 1.000 Testfälle positiv. Der neue Benchmark vergleicht Majority-Baseline, logistische Regression, Decision Tree, Random Forest und Gradient Boosted Trees. Die logistische Regression gewinnt nach Validierungs-Macro-F1 und Balanced Accuracy. Nach dem finalen Refit auf Training plus Validierung lautet die unabhängige Test-Confusion-Matrix: 41 TN, 187 FP, 76 FN und 646 TP. Sie sagt damit beide Klassen voraus und verbessert Macro-F1 um 0,102 sowie Balanced Accuracy um 0,037 gegenüber der Majority-Baseline. Die Accuracy sinkt auf 0,723, weil negative Vorhersagen nicht länger vollständig vermieden werden.

Die Trennung ist messbar, aber nicht stark: Recall für Klasse 0 beträgt nur 0,180. 2.998 von 3.059 positiven Labels erfüllen den synthetischen Folgetag-Vibrationsgrenzwert; 2.726 entstehen ausschließlich daraus. Zusätzlich steigt der Positivanteil zeitlich von 54,51 Prozent im Training auf 76,00 Prozent im Test. Diese Label-Dominanz und der Drift erklären das frühere Ein-Klassen-Verhalten. Druckmerkmale konnten nicht untersucht werden, weil der Quellgenerator keinen Drucksensor enthält. Der vollständige Vergleich mit allen klassenweisen Metriken, Laufzeiten, Feature-Abtrag und Generator-Empfehlungen steht in `docs/ml/CLASSIFICATION_BENCHMARK.md`.

Die Regression schlägt die Mittelwert-Baseline deutlich. Das KMeans-Ergebnis zeigt einen kleinen Anomalie-/Verschleißcluster mit 85 Zeilen sowie zwei größere Lastzustände; eine technische Benennung benötigt weiterhin Domänenvalidierung.

Kein Ergebnis ist eine industrielle Freigabe. Alle Trainingsdaten und Labels sind synthetisch.

## 8. Testergebnisse

- Schnelltests: 17 bestanden, 5 wegen Markierung abgewählt, eine Deprecation-Warnung. Neue Tests prüfen klassenweise Metriken, die Entlarvung einer Ein-Klassen-Vorhersage und ausschließlich validierungsbasierte Threshold-Auswahl.
- Containerintegration: 4 bestanden in 0,82 Sekunden gegen die laufenden Dienste und das Full-Profil.
- Airflow: keine Importfehler; DAG gelistet; Full-DAG erfolgreich.
- Docker Compose: Konfiguration validiert; Images für App, Spark-Submit und Airflow gebaut.
- API: Healthcheck und `/predictions?risk=high` im Container erfolgreich.
- Full-Pipeline lokal: 1.000.000 Messungen in 14,862 Sekunden verarbeitet; dieser Wert misst die lokale Streaming-Baseline, nicht den Spark-Cluster.

## 9. Bekannte Probleme und Grenzen

1. Die Klassifikation trennt beide Klassen nachweisbar besser als die Majority-Baseline, bleibt mit Recall 0,180 für Klasse 0 aber zu schwach für eine fachliche Freigabe.
2. Synthetische Daten belegen keine reale Vorhersageleistung, Sicherheit oder Wirtschaftlichkeit.
3. Eine Million Zeilen ist ein Skalierungsnachweis, aber noch kein zwingender Grund für einen Spark-Cluster.
4. Das lokale Setup verwendet Beispielpasswörter aus `.env.example`; reale Geheimnisse müssen außerhalb von Git verwaltet werden.
5. Kafka/Streaming, HDFS/Object Storage, Modellregistry, Drift-Monitoring, Authentifizierung und Observability-Stack sind Ausbaupunkte.
6. Die GitHub-CLI meldete den konfigurierten Benutzer `Maik-Huebner`, aber dessen Token ist ungültig. Der gewünschte, technisch autorisierte Login ist deshalb nicht verifiziert; es wurde bewusst kein öffentliches Repository erzeugt.

## 10. Dokumentation und Präsentation

Fachdokumentation: `README.md` sowie die Verzeichnisse `docs/architecture`, `docs/databases`, `docs/etl`, `docs/airflow`, `docs/spark`, `docs/ml`, `docs/testing` und `docs/operations`. Die konkrete Tageszuordnung steht in `docs/COURSE_COVERAGE.md`.

Aktualisierte Präsentation: `presentation/Industrial_Intelligence_Platform_2026_Classification_Benchmark.pptx`. Die vorherige Fassung bleibt unverändert erhalten. Sprechertext, Demo, Fallback, Tutorfragen und Lernzusammenfassung liegen daneben als Markdown-Dateien.

## 11. Git, Release-Gates und Veröffentlichung

Die lokalen Release-Gates umfassten Tests, Full-DAG, Compose-Validierung, Gesundheitsprüfungen, Secret-Suche, Größenprüfung und Diff-Check. Folgende abgeschlossene Entwicklungsschritte wurden lokal auf `main` versioniert:

- `1ccd177` – `feat: implement industrial intelligence platform`
- `639580f` – `test: add integration and end-to-end evidence`
- `fecfb51` – `docs: complete documentation and final presentation`
- `7dfd822` – `docs: record validated release status`

Eine abschließende Statusaktualisierung dokumentiert Release-Prüfung und Publikationsblocker. Der vollständige, maßgebliche Stand ist über `git log --oneline` nachvollziehbar.

**GitHub-Repository-URL:** nicht vorhanden. Die Veröffentlichung ist nicht fehlgeschlagen, sondern kontrolliert ausgesetzt, bis `gh auth status` eine gültige und eindeutig autorisierte Identität bestätigt. Es gab keinen Force-Push und keine Annahme eines Benutzernamens.

## 12. Offene Punkte

- GitHub CLI erneut anmelden und Identität prüfen.
- Existenz eines gleichnamigen Repositories kontrollieren.
- Erst dann öffentliches Repository anlegen, `main` pushen und lokalen/remote Commit vergleichen.
- Für einen realen Pilotbetrieb echte Historien, fachlich validierte Labels, Alarmkosten, Security, Monitoring und Betriebs-SLAs ergänzen.
