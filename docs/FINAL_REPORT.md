# Abschlussbericht

**Projekt:** Industrial Intelligence Platform  
**Abnahmedatum:** 19. Oktober 2026  
**Status:** Technische Lösung lokal integriert, gehärtet und getestet; kein GitHub-Push beauftragt oder ausgeführt.

## 1. Implementierungsstatus

Die Plattform ist als integrierte End-to-End-Anwendung umgesetzt. Sie erzeugt deterministische Industriedaten, verteilt diese fachlich auf PostgreSQL, MongoDB, Dateien und Neo4j, validiert und quarantänisiert fehlerhafte Messungen, berechnet Spark-Merkmale, trainiert drei MLlib-Aufgabentypen und stellt Resultate per API bereit. Docker Compose und Airflow verbinden die Komponenten.

| Bereich | Implementiert | Tatsächlich getestet | Ergebnis |
|---|:---:|:---:|---|
| Reproduzierbarer Generator | ja | ja | Full-Profil: 1.000.000 Messungen |
| PostgreSQL | ja | ja | gesund; 50 Maschinen, 950 neue und 1.000 erhaltene ML-Prognosen |
| MongoDB | ja | ja | gesund; 1.000.000 Sensordokumente |
| Neo4j | ja | ja | gesund; 270 Knoten, 400 Beziehungen |
| Python-ETL und Datenqualität | ja | ja | 994.905 valide, 5.095 Quarantänefälle |
| Airflow-DAG | ja | ja | 13 Tasks; beide Gates vor ML/Persistenz; Full-DAG erfolgreich |
| Spark DataFrames/SQL/Joins/Windows/Aggregationen | ja | ja | 4.950 Feature-Zeilen |
| MLlib Klassifikation/Regression/KMeans | ja | ja | echte Kennzahlen gespeichert |
| FastAPI | ja | ja | direkte PostgreSQL-/Neo4j-Zugriffe real abgefragt |
| Tests | ja | ja | 32 Tests bestanden; 1 Host-Spark-Test transparent übersprungen |
| Präsentation und Begleitmaterial | ja | ja | zehn Folien aktualisiert, gerendert und validiert |
| GitHub-Veröffentlichung | nicht beauftragt | nein | kein Push ausgeführt |

## 2. Tatsächlich ausgeführte Services

Die folgende Kombination lief gleichzeitig in Docker Compose: PostgreSQL 16.4, MongoDB 7.0.14, Neo4j 5.23, Spark 3.5.3 Master/Worker, Airflow 2.10.2 Webserver/Scheduler und die FastAPI. Wegen bereits belegter Standardports wurden für den Abnahmelauf ausschließlich Host-Ports geändert: PostgreSQL 65432, MongoDB 57017, Neo4j 57474/57687, API 58000 und Airflow 58080. Die internen Compose-Ports blieben unverändert.

`docker compose ps` meldete API, Airflow-Webserver, PostgreSQL, MongoDB, Neo4j und Spark Master als gesund; Scheduler und Worker liefen. `GET /health` lieferte `{"status":"ok","postgres_available":true,"authentication":"not_configured_local_only"}`. Alle veröffentlichten Ports waren an `127.0.0.1` gebunden.

## 3. Datenbankintegration

- PostgreSQL: 50 Maschinen, 600 Produktionsaufträge, 320 Wartungen, 180 normalisierte Störungsereignisse, 50 Tagesmetriken und 1.950 versionierte ML-Prognosen. Davon gehören 950 zur neuen Benchmark-Version; die 1.000 vorherigen Resultate bleiben erhalten. Upserts verwenden Primärschlüssel und `ON CONFLICT`.
- MongoDB: 1.000.000 verschachtelte Sensordokumente. Der Load verwendet eine temporäre Collection, Zählprüfung und atomaren Rename. Spark liest ausschließlich den kontrollierten, sortierten Snapshot-Export.
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

`industrial_etl` enthält 13 technische Tasks. Ein Source Gate liegt vor Spark; ein Feature Gate liegt vor Metrikberechnung, ML und PostgreSQL-Persistenz. Danach folgen ein finaler Konsistenzcheck und erst dann die erfolgreiche Laufzusammenfassung. Retry, Timeout, ein aktiver Lauf und kleine XCom-Payloads sind konfiguriert.

Am 19. Oktober 2026 wurde der Full-Lauf `hardening_full_20261019T1028Z` ausgeführt. Alle 13 Tasks endeten mit `success`. Die aktive Verarbeitung bis zum finalen Konsistenzcheck dauerte rund 2:33 Minuten. Die Zusammenfassung weist 50 Tagesmetriken, 950 neue Testprognosen, 200 synchronisierte Komponenten-Zeilen und insgesamt 1.950 versionierte PostgreSQL-Prognosen nach. Details und Tasklaufzeiten stehen in `docs/architecture/INTEGRATION_HARDENING_REPORT.md`.

## 6. Spark-Transformation

Der Spark-Lauf las 1.000.000 Messungen aus dem kontrollierten MongoDB-Export, normalisierte Typen und Zeitstempel, filterte ungültige Werte und entfernte Duplikate. DataFrame-Operationen, Spark SQL, mehrere Joins, `lag`, rollender Mittelwert, `lead`, Ranking und Aggregationen sind im selben Feature-Engineering-Pfad integriert. Ergebnis: 994.905 valide Messungen und 4.950 tagesbezogene Feature-Zeilen für 50 Maschinen. Die Ausgabe liegt partitioniert als Parquet vor.

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

- Gesamtsuite: 32 Tests bestanden, eine Deprecation-Warnung.
- Spark-Vertragstest: auf dem Host ohne PySpark explizit übersprungen; der identische Transformationspfad lief im Full-DAG erfolgreich.
- Containerintegration: 4 Tests gegen die laufenden Dienste und das Full-Profil bestanden.
- Airflow: keine Importfehler; DAG gelistet; Full-DAG erfolgreich.
- Docker Compose: Konfiguration validiert; Images für App, Spark-Submit und Airflow gebaut.
- API: Healthcheck, Maschinen, Metriken, versionierte Prognosen, Pipeline-Läufe und Neo4j-Abhängigkeiten gegen reale Dienste erfolgreich.
- Full-DAG: 1.000.000 Messungen, alle 13 Tasks erfolgreich; aktive Laufzeit bis zum finalen Check rund 2:33 Minuten.

## 9. Bekannte Probleme und Grenzen

1. Die Klassifikation trennt beide Klassen nachweisbar besser als die Majority-Baseline, bleibt mit Recall 0,180 für Klasse 0 aber zu schwach für eine fachliche Freigabe.
2. Synthetische Daten belegen keine reale Vorhersageleistung, Sicherheit oder Wirtschaftlichkeit.
3. Eine Million Zeilen ist ein Skalierungsnachweis, aber noch kein zwingender Grund für einen Spark-Cluster.
4. Die API besitzt keine Authentifizierung, TLS-Terminierung oder Rate Limits und darf nicht öffentlich exponiert werden.
5. Das lokale Setup verwendet Beispielpasswörter aus `.env.example`; reale Geheimnisse müssen außerhalb von Git verwaltet werden.
6. Kafka/Streaming, HDFS/Object Storage, Modellregistry, Drift-Monitoring und ein Observability-Stack sind Ausbaupunkte.

## 10. Dokumentation und Präsentation

Fachdokumentation: `README.md` sowie die Verzeichnisse `docs/architecture`, `docs/databases`, `docs/etl`, `docs/airflow`, `docs/spark`, `docs/ml`, `docs/testing` und `docs/operations`. Die konkrete Tageszuordnung steht in `docs/COURSE_COVERAGE.md`.

Aktuellste Präsentation: `presentation/Industrial_Intelligence_Platform_2026_Integration_Hardening_Final_v2.pptx`. Sie zeigt MongoDB als verifizierte Spark-Quelle, beide Gates vor ML/Persistenz und den direkten PostgreSQL-/Neo4j-Serving-Pfad. Alle zehn Folien wurden gerendert und visuell geprüft; Paket-, Layout-, Font- und Chartvalidierung bestanden. Die vorherigen Fassungen bleiben unverändert erhalten.

## 11. Git und Release-Gates

Die Integrationshärtung wurde auf dem eigenen Branch `feature/pipeline-integration-hardening` durchgeführt. Die lokalen Gates umfassen Tests, Full-DAG, Compose-Validierung, reale API-/Datenbankprüfungen, Präsentationsvalidierung und `git diff --check`. Bestehende Berichte, Modelle und 1.000 historische Prognosen wurden nicht ungeprüft überschrieben. Es wurde kein GitHub-Push ausgeführt.

## 12. Offene Punkte

- Für einen realen Pilotbetrieb echte Historien, fachlich validierte Labels, Alarmkosten, Security, Monitoring und Betriebs-SLAs ergänzen.
- Authentifizierung, TLS, Rate Limits, Secret Store und Backup-/Restore-Nachweis vor externer Freigabe ergänzen.
