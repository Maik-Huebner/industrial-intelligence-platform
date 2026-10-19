# Klassifikations-Benchmark

**Messdatum:** 19. Oktober 2026
**Datensatz:** 4.950 synthetische Maschinen-Tage aus 1.000.000 Rohmessungen
**Maßgebliche Artefakte:** `reports/classification_data_audit.json` und `reports/classification_benchmark.json`

## Ergebnis in einem Satz

Die finale logistische Regression erkennt erstmals beide Klassen und übertrifft die Majority-Baseline bei Macro-F1, Balanced Accuracy, PR-AUC und ROC-AUC. Die Trennschärfe ist nachweisbar, aber wegen nur 17,98 Prozent Recall für Klasse 0 und synthetischer Daten noch nicht produktionsreif.

## Unabhängiger Testsatz

Der Split erfolgt auf 99 unterschiedlichen Tagen chronologisch. Training umfasst 11. Juli bis 7. September, Validierung 9. bis 27. September und Test 29. September bis 17. Oktober. Der 8. und 28. September werden als Purge-Tage ausgelassen. Das ist erforderlich, weil das Label mit `lead(1)` den Folgetag verwendet. So reicht kein Target-Horizont über eine Split-Grenze.

Alle 50 bekannten Maschinen kommen in allen Zeitabschnitten vor. Das entspricht dem Einsatzziel „zukünftiger Zustand bereits bekannter Anlagen“. Für die Generalisierung auf völlig neue Maschinen wäre zusätzlich ein gerätebasierter Holdout erforderlich.

| Split | Klasse 0 | Klasse 1 | Gesamt | Positivanteil |
|---|---:|---:|---:|---:|
| Training | 1.342 | 1.608 | 2.950 | 54,51 % |
| Validierung | 293 | 657 | 950 | 69,16 % |
| Test | 228 | 722 | 950 | 76,00 % |

Die Verteilung zeigt einen deutlichen zeitlichen Drift. Deshalb wäre ein zufälliger Split zu optimistisch und wird nicht für Auswahl oder Kennzahlen verwendet.

## Modellvergleich auf dem unangetasteten Test

Parameter und Schwellenwerte wurden ausschließlich anhand von Training und Validierung festgelegt. Die Modellauswahl basiert auf Validierungs-Macro-F1, danach Balanced Accuracy, und verlangt Vorhersagen beider Klassen.

| Modell | Acc. | P0 | R0 | P1 | R1 | Macro-F1 | Bal. Acc. | PR-AUC | ROC-AUC | Train / Tuning s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Majority-Baseline | 0,760 | 0,000 | 0,000 | 0,760 | 1,000 | 0,432 | 0,500 | 0,760 | 0,500 | 0,000 / 0,000 |
| Logistic Regression | 0,745 | 0,383 | 0,101 | 0,770 | 0,949 | 0,505 | 0,525 | 0,855 | 0,632 | 1,419 / 4,898 |
| Decision Tree | 0,467 | 0,191 | 0,377 | 0,716 | 0,496 | 0,420 | 0,437 | 0,745 | 0,431 | 0,746 / 1,549 |
| Random Forest | 0,680 | 0,247 | 0,162 | 0,761 | 0,843 | 0,498 | 0,503 | 0,745 | 0,472 | 0,753 / 0,753 |
| Gradient Boosted Trees | 0,583 | 0,244 | 0,351 | 0,762 | 0,657 | 0,497 | 0,504 | 0,746 | 0,482 | 2,824 / 2,824 |

Die Training-Zeit bezeichnet den ausgewählten Kandidaten, die Tuning-Zeit die Summe aller Kandidaten derselben Modellfamilie. AUC-Werte der konstanten Baseline sind Referenzwerte ohne Ranking-Nutzen.

## Final integriertes Modell

Die logistische Regression erzielte auf der Validierung Macro-F1 0,573 und Balanced Accuracy 0,582; die Majority-Baseline erreichte dort 0,409 und 0,500. Ausgewählt wurden `regParam=0.05`, `elasticNetParam=0.5`, inverse Klassen­gewichte und der ausschließlich auf der Validierung optimierte Schwellenwert 0,58. Danach wurde genau diese Konfiguration auf Training plus Validierung neu gefittet.

Finale Test-Confusion-Matrix:

| | vorhergesagt 0 | vorhergesagt 1 |
|---|---:|---:|
| tatsächlich 0 | 41 | 187 |
| tatsächlich 1 | 76 | 646 |

Das finale Modell erreicht Accuracy 0,723, Macro-F1 0,534, gewichtetes F1 0,689, Balanced Accuracy 0,537, PR-AUC 0,855 und ROC-AUC 0,632. Gegenüber der Test-Baseline steigt Macro-F1 um 0,102 und Balanced Accuracy um 0,037. Die geringere Accuracy ist kein Rückschritt: Sie entsteht, weil das Modell nicht mehr jede Zeile als positiv klassifiziert.

Das Modell liegt unter `models/classification_best_pipeline.model`. Die 950 API-kompatiblen Testvorhersagen verwenden `model_name=logistic_regression` und `model_version=synthetic-v2-classification-benchmark`.

## Feature Engineering und Leakage-Prüfung

- Aktuelle Tagesaggregate sagen den Folgetag voraus.
- Historische Mittelwerte verwenden ausschließlich `rowsBetween(-7, -1)`; der aktuelle oder zukünftige Target-Tag fließt nicht in das Fenster ein.
- Hinzu kamen 1-Tages-Änderungen, Abweichungen vom vorherigen 7-Tage-Niveau und zyklische Wochentagsmerkmale.
- Logistische Regression skaliert numerische Merkmale. Baumverfahren erhalten unskalierte Vektoren.
- Maschinentypen werden one-hot codiert, nicht als künstlich geordnete Zahl behandelt.
- `future_*`-Spalten und `risk_rank` sind explizit ausgeschlossen.
- Die Basis-Logistic erreichte auf der Validierung Macro-F1 0,561 und Balanced Accuracy 0,560. Mit den neuen Merkmalen stiegen diese Werte auf 0,573 und 0,582.

Die stärksten linearen Feature-Label-Korrelationen sind der vorherige 7-Tage-Mittelwert der Vibration (0,245), der vorherige 7-Tage-Mittelwert der Temperatur (0,245), die aktuelle mittlere Vibration (0,240) und die aktuelle mittlere Temperatur (0,228). Korrelation ist dabei keine Kausalität. Bei Random Forest und Decision Tree rangiert der vorherige 7-Tage-Temperaturmittelwert an erster Stelle der Importance; GBT gewichtet die 7-Tage-Vibrationsabweichung am stärksten.

## Ursache der alten Ein-Klassen-Vorhersage

Das alte Modell wurde auf 3.950 Zeilen trainiert und direkt auf 1.000 spätere Zeilen getestet. Im Test waren 760 Zeilen positiv; alle 1.000 Vorhersagen waren positiv. Accuracy 0,760 und gewichtetes F1 0,656 verdeckten damit Recall 0 für Klasse 0.

Drei Effekte wirken zusammen:

1. Der Positivanteil steigt zeitlich von 54,51 auf 76,00 Prozent.
2. 2.998 der 3.059 positiven Labels erfüllen den Grenzwert `future_max_vibration_mm_s > 7.5`; 2.726 Positive entstehen ausschließlich durch diese Bedingung. Der Zielwert wird somit fast vollständig von einem breiten synthetischen Schwellwert dominiert.
3. Es gab weder Validierungssatz noch Macro-F1, Balanced Accuracy oder Threshold-Optimierung als Auswahlkriterium.

## Grenzen und separate Generator-Empfehlung

Die erreichte Trennung ist statistisch sichtbar, aber schwach. Besonders Klasse 0 bleibt mit Recall 0,180 schwierig. Der Datensatz belegt weder reale Wartungsqualität noch kausale Vorläufer von Ausfällen. Ein Drucksensor existiert im Quellschema nicht; Druckabweichungen konnten daher nicht seriös untersucht werden.

Für eine neue, separat versionierte synthetische Datenversion empfiehlt sich:

1. Druck als Sensor mit physikalisch plausibler Kopplung an Last, Hydraulikfehler und Wartung ergänzen.
2. Ausfälle aus mehrtägigen latenten Verschleißtrajektorien mit Rauschen und Wartungs-Reset generieren, statt das Label fast vollständig aus einem einzelnen Maximalwert abzuleiten.
3. Alarm- und Ausfallkosten vor der Modellierung festlegen und den Zielhorizont fachlich definieren.
4. Neue Maschinenprofile und einen gerätebasierten Holdout ergänzen.
5. Die neue Datenversion vor Modelltraining einfrieren; der aktuelle Test wird weder verändert noch zur Generatorabstimmung verwendet.
