# MLlib-Methodik und Report

## Klassifikation

Logistische Regression und Entscheidungsbaum klassifizieren erhöhten Wartungsbedarf. `StringIndexer`, `VectorAssembler` und `StandardScaler` laufen in einer echten Pipeline. Nur Trainingsdaten werden gefittet. Accuracy, gewichtete Precision, Recall, F1 und Konfusionsmatrix werden aus Testvorhersagen berechnet.

## Regression

Lineare Regression prognostiziert die mittlere Temperatur des Folgetags. Das Target ist kein Eingabefeature. RMSE und MAE werden mit einer Trainingsmittelwert-Baseline verglichen.

## Clustering

KMeans clustert standardisierte Betriebskennzahlen in drei Gruppen. Der Report enthält Silhouette, Verteilung, skalierte Zentren und die unskalierten Profilmittelwerte. Eine technische Benennung erfolgt erst nach Sichtung dieser Mittelwerte.

## Validierung

Die berichteten Metriken verwenden einen chronologischen 80/20-Holdout. `randomSplit` wird zusätzlich ausgeführt und mit Mengen protokolliert, dient aber nicht als berichtete Zeitreihenvalidierung. `reports/ml_report.json` wird nur von einer echten Spark-Ausführung geschrieben.

