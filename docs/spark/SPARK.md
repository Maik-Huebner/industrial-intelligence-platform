# Apache Spark

`spark_jobs/transform.py` erstellt eine `SparkSession`, liest JSON und CSV, normalisiert verschachtelte Felder und demonstriert `select`, `filter`, `withColumn`, `dropDuplicates`, `groupBy`, `agg` und `orderBy`.

Window Functions liefern vorherige Temperatur, Delta, rollenden Zwölf-Messwerte-Mittelwert, zukünftige Targets und tägliche Risikoränge. Inner und Left Joins verbinden Maschinenstamm, Wartung und Störungen. Eine temporäre View und Spark SQL erzeugen Linienkennzahlen. Parquet partitioniert die Features nach Datum.

Lazy Evaluation bleibt erhalten, bis Schreiboperationen und `count()`-Actions den Plan ausführen. Eine Million Zeilen kann ein einzelner Rechner verarbeiten; Spark wird hier wegen des Unterrichtsziels und der späteren Skalierung auf längere Historien, mehr Sensoren und komplexe Joins eingesetzt.

