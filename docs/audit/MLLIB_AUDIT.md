# Spark-MLlib-Audit

Stand: 19. Oktober 2026  
Primärquelle: `reports/ml_report.json`, erzeugt im realen Full-Spark-Lauf am 19. Oktober 2026 um 11:17 UTC.

## Kurzurteil

Alle drei MLlib-Pfade sind ausführbar und methodisch getrennt. Die Klassifikation sagt beide Klassen voraus und übertrifft die Majority-Baseline bei Macro-F1 und Balanced Accuracy, besitzt aber nur geringe zusätzliche Trennschärfe. Regression und Clustering sind technisch plausibel; auch sie sind wegen synthetischer Daten nicht als industriell validierte Modelle zu verstehen.

## Klassifikation

### Ziel und Split

Das binäre Ziel beschreibt ein erhöhtes Risiko am Folgetag. Es wird aus `lead(1)` gebildet. Der Split ist chronologisch 60/20/20 und entfernt an beiden Grenzen je einen vollständigen Tag:

- Training: 11.07.–07.09.2026, 2.950 Zeilen.
- Purge: 08.09.2026.
- Validierung: 09.09.–27.09.2026, 950 Zeilen.
- Purge: 28.09.2026.
- Test: 29.09.–17.10.2026, 950 Zeilen.

Modell, Hyperparameter und Threshold werden ausschließlich anhand von Training und Validierung gewählt. `test_was_used_for_selection` ist im Report `false`. Danach wird das festgelegte Modell auf Training plus Validierung neu trainiert und genau einmal am Test bewertet.

### Feature- und Leakage-Prüfung

Verwendet werden aktuelle Tageswerte, ausschließlich rückwärtsgerichtete 7-Tage-Mittel, eintägige Änderungen, Abweichungen von der Historie, zyklische Wochentagsmerkmale, Anlagenalter, Kritikalität, Wartungszahl und one-hot-kodierter Maschinentyp. Druck ist im Quellschema nicht vorhanden und wurde nicht erfunden.

Ausgeschlossen sind `future_avg_temperature_c`, `future_failure_count`, `future_anomaly_rate`, `future_max_vibration_mm_s` und `risk_rank`. Rollende Fenster enden am Vortag. `StringIndexer`, `OneHotEncoder`, `VectorAssembler`, `StandardScaler` und Klassengewichte werden im Pipeline-/Trainingspfad auf Trainingsdaten angepasst. Im Audit wurde keine Zielinformation in den Features gefunden.

### Modellvergleich

Die Tabelle zeigt die auf Validierung gewählte Konfiguration und den zugehörigen, vor dem finalen Refit gemessenen Testwert. Trainingszeiten sind Messwerte dieser Ausführung und keine allgemeine Laufzeitgarantie.

| Modell | Threshold | Training | Tuning | Validierung Macro-F1 | Test Macro-F1 | Test Balanced Accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Majority-Baseline | – | 0,000 s | 0,000 s | 0,409 | 0,432 | 0,500 |
| Logistische Regression | 0,58 | 1,217 s | 4,707 s | **0,573** | **0,505** | **0,525** |
| Decision Tree | 0,44 | 0,789 s | 1,629 s | 0,467 | 0,420 | 0,437 |
| Random Forest | 0,58 | 0,762 s | 0,762 s | 0,537 | 0,486 | 0,486 |
| Gradient Boosted Trees | 0,56 | 2,892 s | 2,892 s | 0,476 | 0,497 | 0,504 |

Auswahlregel: höchste Validierungs-Macro-F1, danach Balanced Accuracy; beide Klassen müssen vorhergesagt werden. Die logistische Regression gewinnt diese Regel. Nach dem regelkonformen Refit auf Training plus Validierung dauerte das Training 2,532 Sekunden.

### Finale unabhängige Testmessung

| Kennzahl | Wert |
|---|---:|
| Accuracy | 0,723 |
| Macro-F1 | 0,534 |
| Balanced Accuracy | 0,537 |
| PR-AUC | 0,855 |
| ROC-AUC | 0,632 |
| Klasse 0: Precision / Recall / F1 | 0,350 / 0,180 / 0,238 |
| Klasse 1: Precision / Recall / F1 | 0,776 / 0,895 / 0,831 |
| Confusion Matrix | TN 41, FP 187, FN 76, TP 646 |

Die Majority-Baseline erreicht 0,760 Accuracy, aber nur 0,432 Macro-F1, 0,500 Balanced Accuracy und erkennt kein einziges negatives Beispiel. Die finale Regression ist deshalb fachlich geeigneter, obwohl ihre Accuracy niedriger ist. Der Gewinn bei Balanced Accuracy beträgt nur 0,037; insbesondere der Recall von Klasse 0 ist mit 0,180 schwach. Das Modell ist ein transparenter Ausbildungsnachweis, keine Freigabe für Wartungsentscheidungen.

## Regression

Das Ziel ist die durchschnittliche Temperatur des Folgetags. Die lineare Regression verwendet einen chronologischen 80/20-Split. Der Audit fand einen Grenzfehler: Vor der Korrektur konnte das `lead(1)`-Ziel der letzten Trainingszeile bereits im Testzeitraum liegen. Jetzt wird der Grenztag 27.09.2026 entfernt.

- 4.950 Featurezeilen insgesamt.
- 3.900 Training, 50 Purge, 1.000 Test.
- RMSE 0,514 °C, MAE 0,439 °C.
- Mittelwert-Baseline RMSE 3,557 °C.

Zielspalte und übrige Zukunftsspalten werden nicht assembliert. Das Resultat ist auf den stark glatten synthetischen Verlauf plausibel, aber nicht auf echte Sensorik übertragbar. Der neue Test `test_regression_split_purges_the_lead_target_boundary` sichert die zeitliche Grenze ab.

## Clustering

KMeans nutzt zehn numerische Merkmale, `VectorAssembler`, `StandardScaler` und `k=3`. Der gemessene Silhouette Score beträgt 0,554. Die Verteilung auf dem 3.900-Zeilen-Trainingsanteil lautet 3.576 / 244 / 80.

Der kleine Cluster mit 80 Zeilen zeigt im synthetischen Datensatz hohe Anomalierate, Temperatur und Vibration. Dies ist eine deskriptive Beobachtung, keine fachlich validierte Zustandsklasse. Die Cluster werden daher nur nummeriert. Wartungs- oder Gefahrennamen wären ohne Domänenvalidierung unzulässig.

## Pipeline-Stufen

| Komponente | Verwendung | Urteil |
|---|---|---|
| `StringIndexer` / `OneHotEncoder` | Maschinentyp in der Klassifikation | PASS |
| `VectorAssembler` | Featurevektor aller drei Pfade | PASS |
| `StandardScaler` | Klassifikation und KMeans | PASS |
| `LogisticRegression` | ausgewählter Klassifikator | PASS |
| `DecisionTreeClassifier` | Benchmark | PASS |
| `RandomForestClassifier` | Benchmark | PASS |
| `GBTClassifier` | Benchmark | PASS |
| `LinearRegression` | Folgetagstemperatur | PASS |
| `KMeans` | explorative Segmentierung | PASS |
| `Pipeline` / `PipelineModel` | train-only Fit, Transformation und Speicherung | PASS |
| binäre und Regressions-Evaluatoren plus eigene Metriken | AUC, RMSE/MAE, klassenweise Werte und Confusion Matrix | PASS |

Modellspeicherung für Regression und KMeans verwendet nun wie die Klassifikation explizit `overwrite()`. Damit können Wiederholungen nicht unbemerkt ein veraltetes Modellverzeichnis stehen lassen.

## Reproduzierbarkeit und Grenzen

- Generator, Splits und Modellkonfigurationen sind deterministisch versioniert; Laufzeitwerte können je Host schwanken.
- Full-Training und Container-Vertragstest wurden mit Spark 3.5.3 ausgeführt.
- Der Host-PySpark-Test blieb erwartungsgemäß übersprungen, da PySpark dort nicht installiert ist; der vorgesehene Containerpfad bestand denselben Vertrag.
- Es fehlen reale Labels, Kostenmatrix, Driftprüfung, Kalibrierungsmonitoring, Modellregistry, Champion/Challenger-Prozess und fachliche Freigabe.
- Die PR-AUC wird durch die positive Mehrheitsklasse begünstigt und darf nicht isoliert interpretiert werden.

**MLlib-Gesamtstatus: PASS für Ausbildung und Portfolio; NOT READY für reale industrielle Entscheidungsunterstützung.**
