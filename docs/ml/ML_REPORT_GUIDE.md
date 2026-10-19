# MLlib-Methodik und Report

## Klassifikation

Eine Majority-Class-Baseline, logistische Regression, Entscheidungsbaum, Random Forest und Gradient Boosted Trees klassifizieren erhöhten Wartungsbedarf. `StringIndexer`, `OneHotEncoder`, `VectorAssembler` und bei der logistischen Regression `StandardScaler` laufen in echten Spark-Pipelines. Während Tuning und Auswahl werden inverse Klassen­gewichte ausschließlich aus dem Training berechnet. Nach dem Lock der Konfiguration berechnet der finale Refit die Gewichte auf Training plus Validierung neu. Der vollständige Vergleich einschließlich klassenweiser Precision, Recall und F1, Macro-F1, Balanced Accuracy, PR-AUC, ROC-AUC, Confusion Matrix und Laufzeiten steht in `CLASSIFICATION_BENCHMARK.md`.

## Regression

Lineare Regression prognostiziert die mittlere Temperatur des Folgetags. Das Target ist kein Eingabefeature. RMSE und MAE werden mit einer Trainingsmittelwert-Baseline verglichen.

## Clustering

KMeans clustert standardisierte Betriebskennzahlen in drei Gruppen. Der Report enthält Silhouette, Verteilung, skalierte Zentren und die unskalierten Profilmittelwerte. Eine technische Benennung erfolgt erst nach Sichtung dieser Mittelwerte.

## Validierung

Die Klassifikation verwendet einen chronologischen 60/20/20-Split mit je einem Purge-Tag zwischen Training, Validierung und Test. Das verhindert, dass das mit `lead(1)` gebildete Label über Split-Grenzen reicht. Parameter und Schwellenwerte werden nur auf Training und Validierung bestimmt; der Test entscheidet nicht über die Modellauswahl. Regression und KMeans verwenden einen purged chronologischen 80/20-Pfad mit 3.900 Trainings-, 50 ausgelassenen Grenz- und 1.000 Testzeilen. `randomSplit` bleibt eine Unterrichtsdemonstration ohne Einfluss auf berichtete Modellentscheidungen.

`reports/classification_data_audit.json` dokumentiert Verteilung, Label-Ursachen und Korrelationen. `reports/classification_benchmark.json` enthält den vollständigen Modellvergleich. `reports/ml_report.json` verbindet Klassifikation, Regression und Clustering aus dem gemessenen Lauf.
