# Tutorfragen mit belastbaren Antworten

## 1. Warum drei Datenbanken?

Die Zugriffsmuster sind verschieden: PostgreSQL schützt strukturierte Fakten und Ergebnisdaten, MongoDB speichert hochvolumige verschachtelte Sensordokumente, Neo4j beantwortet mehrstufige Beziehungsfragen. Dieselbe Information wird nicht wahllos verdreifacht.

## 2. Warum nicht alle Sensordaten in Neo4j?

Eine Million Messknoten würden Speicher und Traversierungen belasten, ohne die fachlichen Abhängigkeitsfragen zu verbessern. Der Graph hält 50 Maschinen, 220 Komponenten und 400 Beziehungen; Zeitreihen bleiben in MongoDB und Parquet.

## 3. Liest Spark MongoDB wirklich?

Ja. MongoDB ist die aktive Sensorquelle. Der Code exportiert die aktive Collection gezählt, nach `reading_id` sortiert und prüfbar in einen Snapshot. Spark liest diesen konsistenten Snapshot. Ein direkter Spark-Mongo-Connector wurde bewusst nicht benötigt.

## 4. Wie ist Reproduzierbarkeit sichergestellt?

Fester Seed, deterministische IDs und Zeitverläufe, versionierte Abhängigkeiten, definierte Profile sowie idempotente Upserts und `MERGE`. Zusätzlich bestand ein isolierter Fresh-Start mit eigenen Volumes und zwei vollständigen 13-Task-Läufen.

## 5. Wie verhindert die Pipeline Data Leakage?

Rückwärtsgerichtete Fenster enden am Vortag. Labels und Regressionsziel entstehen mit `lead(1)` aus dem Folgetag und sind keine Features. Zwischen Training, Validierung und Test liegt jeweils ein Purge-Tag. Der Audit ergänzte denselben Schutz für die Regression.

## 6. Warum war 76 Prozent Accuracy schlecht?

Im Test sind 76 Prozent der Zeilen positiv. Eine reine Positivvorhersage erreicht deshalb 0,760 Accuracy, erkennt aber kein negatives Beispiel. Ihre Balanced Accuracy ist 0,500 und Macro-F1 0,432. Die finale logistische Regression sagt beide Klassen voraus und erreicht 0,537 beziehungsweise 0,534.

## 7. Ist eine Balanced Accuracy von 0,537 gut?

Nein, sie ist nur knapp besser als Zufalls-/Majority-Niveau. Sie erfüllt das technische Erfolgskriterium der Trennung, belegt aber keine Einsatzreife. Besonders Klasse 0 bleibt mit Recall 0,180 schwach.

## 8. Warum wurde die logistische Regression gewählt?

Die festgelegte Auswahlregel priorisiert Validierungs-Macro-F1, danach Balanced Accuracy, und verlangt Vorhersagen beider Klassen. Mit Macro-F1 0,573 auf der Validierung lag die logistische Regression vor den Baumverfahren. Der Test wurde nicht zur Auswahl verwendet.

## 9. Warum ist die PR-AUC mit 0,855 so hoch?

Die positive Klasse ist im Test mit 722 von 950 Fällen die Mehrheit. PR-AUC hängt von der Klassenprävalenz ab. Deshalb wird sie nur zusammen mit Confusion Matrix, klassenweisen Werten, Macro-F1 und Balanced Accuracy interpretiert.

## 10. Wurde der Threshold am Test optimiert?

Nein. Threshold 0,58 und Hyperparameter wurden ausschließlich auf Training und Validierung gewählt. Erst danach wurde das Modell auf Training plus Validierung neu angepasst und einmal auf dem unabhängigen Test ausgewertet.

## 11. Warum gibt es `randomSplit` im Report?

Nur als ausdrücklich markierte Unterrichtsdemonstration. `random_split_used_for_metrics` ist `false`. Die veröffentlichten Klassifikations- und Regressionsmetriken stammen aus chronologischen, um den Target-Horizont bereinigten Splits.

## 12. Was bedeutet der Regressionswert?

Die lineare Regression prognostiziert die durchschnittliche Temperatur des Folgetags und erreicht RMSE 0,514 °C sowie MAE 0,439 °C. Die Mittelwert-Baseline liegt bei RMSE 3,557 °C. Der starke Abstand profitiert vom glatten synthetischen Verlauf und ist keine Aussage über reale Sensorik.

## 13. Was bedeutet die KMeans-Silhouette 0,554?

Die drei Cluster sind im verwendeten standardisierten synthetischen Merkmalsraum sichtbar getrennt. Der kleine 80-Zeilen-Cluster besitzt hohe Anomalierate, Temperatur und Vibration. Ohne Domänenprüfung erhält er trotzdem keinen Namen wie „kritischer Ausfall“.

## 14. Was machen die beiden Quality Gates?

Das Source Gate prüft Quellcount, IDs, Maschinenreferenzen, Fehlergründe und Quarantänequote vor Spark. Das Feature Gate prüft Featurezahl, Maschinenabdeckung, Nullschlüssel/-ziele, Klassen je Split und Splitgrenzen vor ML und Ergebnis-Persistenz.

## 15. Was passiert bei wiederholtem DAG-Lauf?

Stammdaten, Metriken und Graphdaten werden idempotent aktualisiert. Prognosen derselben Modellversion werden upserted; andere Versionen bleiben historisch erhalten. Im Full-Bestand liegen deshalb 1.000 alte und 950 neue Prognosen statt unkontrollierter Duplikate.

## 16. Was wurde tatsächlich ausgeführt?

Der Full-DAG `hardening_full_20261019T1028Z` verarbeitete eine Million Sensordokumente mit 13/13 erfolgreichen Tasks. Zusätzlich liefen in einer isolierten Umgebung ein geplanter und ein manueller Small-DAG vollständig. 32 Tests sowie zwei Spark-Vertragsprüfungen im Spark-3.5.3-Container bestanden.

## 17. Warum Spark bei nur einer Million Zeilen?

Eine Million Zeilen rechtfertigen wirtschaftlich nicht automatisch Spark. Das Projekt demonstriert denselben verteilbaren Codepfad für DataFrames, SQL, Joins, Fenster, Aggregationen, Parquet und MLlib. Eine Skalierungs- oder Performancebehauptung wird daraus ausdrücklich nicht abgeleitet.

## 18. Warum wurde der Host-PySpark-Test übersprungen?

PySpark ist keine benötigte Host-Abhängigkeit; die vorgesehene Umgebung ist der versionierte Spark-Container. Der identische Normalisierungs- und Splitvertrag wurde dort mit Spark 3.5.3 ausgeführt und bestanden.

## 19. Ist die API sicher?

Nur für die lokale Demo. Alle Ports binden standardmäßig an `127.0.0.1`, Abfragen sind parametrisiert und Eingaben typisiert. Authentifizierung, Autorisierung, TLS und Rate Limits fehlen jedoch. Deshalb ist ein öffentlich erreichbarer Betrieb nicht freigegeben.

## 20. Darf das Repository öffentlich werden?

Der geprüfte Quellstand ja: Es wurden keine realen Secrets, privaten Schlüssel, `.env`-Dateien, großen Datensätze, Modellartefakte, personenbezogenen Daten oder fremden Unterrichtsnotebooks in Tree oder Historie gefunden. Ein Push wurde nicht ausgeführt und benötigt ein letztes Clean-/Secret-/Test-Gate.

## 21. Was war der wichtigste Auditfund?

Das Regressionsziel mit `lead(1)` konnte am alten 80/20-Split einen Tag über die Train-/Test-Grenze reichen. Der Grenztag wird jetzt entfernt, die Metadaten nennen dies explizit, und ein automatisierter Test schützt die Regel.

## 22. Was fehlt vor Produktion?

Echte governance-geprüfte Historien, fachlich validierte Labels und Kostenmatrix; AuthN/AuthZ, TLS, Rate Limits und Secret Store; unprivilegierte Container, SBOM/CVE-Scan, Backups, Monitoring und SLOs; Modellregistry, Drift-Erkennung, Rollback, Last-/Recovery-Tests und ein kontrollierter Pilotbetrieb.
