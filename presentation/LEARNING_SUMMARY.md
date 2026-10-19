# Lernzusammenfassung

## In einem Satz

Die Industrial Intelligence Platform zeigt, wie heterogene Industriedaten reproduzierbar erzeugt, qualitätsgesichert, polyglott gespeichert, mit Airflow orchestriert, mit Spark verarbeitet und mit MLlib ehrlich bewertet werden.

## Merkpunkte

- **PostgreSQL:** strukturierte Fakten, Constraints, analytische SQL-Abfragen, Upserts.
- **MongoDB:** flexible verschachtelte Sensordokumente, Indizes und Batch-Upserts.
- **Neo4j:** Anlagen- und Komponentenbeziehungen, Constraints, `MERGE`, Traversierungen.
- **ETL:** Extract aus mehreren Formaten, reason-coded Quarantäne, idempotentes Load.
- **Airflow:** Orchestrierung statt Datentransport; XCom nur für kleine Metadaten.
- **Spark:** DataFrames, SQL, Joins, Windows, Aggregationen und partitioniertes Parquet.
- **MLlib:** Pipeline-Stages, Klassifikation, Regression, KMeans und persistierte Modelle.
- **Validierung:** Training, Validierung und Test chronologisch trennen; Purge-Tage an den Grenzen des Target-Horizonts einsetzen.
- **Evaluation:** Confusion-Matrix und Baselines sind oft aussagekräftiger als eine einzelne Kennzahl.
- **Engineering:** Gesundheitsprüfungen, Tests, reproduzierbare Profile und ehrliche Grenzen gehören zum Ergebnis.

## Zahlen, die sitzen sollten

- 1.000.000 erzeugte Messungen
- 994.905 valide, 5.095 quarantänisiert
- 4.950 Spark-Tagesfeatures
- 50 Maschinen, fünf Linien
- 1.000 gespeicherte ML-Prognosen
- Regression: RMSE 0,521 °C gegenüber Baseline 3,536 °C
- KMeans: Silhouette 0,362
- Klassifikation final: Macro-F1 0,534 statt 0,432; Balanced Accuracy 0,537 statt 0,500
- Confusion Matrix final: 41 TN, 187 FP, 76 FN, 646 TP
- 17 schnelle und 4 Containerintegrationstests bestanden

## Drei ehrliche Grenzen

1. Synthetische Daten sind kein Nachweis realer Wartungsgüte.
2. Die Klassifikation trennt beide Klassen, aber Klasse 0 erreicht nur Recall 0,180.
3. Eine Million Zeilen demonstrieren Skalierbarkeit, erzwingen aber noch keine Clusterarchitektur.
