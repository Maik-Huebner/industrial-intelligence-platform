# Präsentationsnotizen zur gehärteten End-to-End-Pipeline

## Erklärung in ungefähr zwei Minuten

Die Industrial Intelligence Platform bildet eine vollständige lokale Batch-Pipeline für Predictive Maintenance ab. Ein deterministischer Generator erzeugt 50 Maschinen, 600 Produktionsaufträge, Wartungen, Störungen und eine Million verschachtelte Sensordokumente.

PostgreSQL speichert strukturierte Fakten, Tagesmetriken, versionierte Prognosen und Pipeline-Läufe. MongoDB ist die operative Sensorquelle. Neue Daten werden zuerst vollständig in eine temporäre Collection geladen, gezählt und erst dann atomar aktiviert. Ein sortierter, kontrollierter Export speist Spark. Neo4j modelliert Maschinen, Komponenten und gemeinsame technische Abhängigkeiten.

Airflow orchestriert 13 Tasks. Das Source Gate liegt vor Spark und prüft Mengen, IDs, Maschinenreferenzen und Quarantänequote. Spark normalisiert den MongoDB-Export, erzeugt 4.950 Tagesfeatures und trennt Training, Validierung und Test chronologisch mit Purge-Tagen. Das Feature Gate prüft Schema, Nullwerte, Maschinenabdeckung und beide Klassen in jedem Split, bevor Metriken, ML und PostgreSQL-Persistenz starten.

Das finale logistische Modell erreicht Macro-F1 0,534 und Balanced Accuracy 0,537 gegenüber 0,432 beziehungsweise 0,500 der Majority-Baseline. Es sagt beide Klassen voraus, erkennt negative Fälle aber weiterhin schwach. Deshalb ist das Ergebnis eine messbare Verbesserung, keine Produktionsfreigabe.

FastAPI liest PostgreSQL und Neo4j direkt. Prognosen sind versioniert und paginiert; Maschinenabhängigkeiten stammen aus parametrierten Cypher-Abfragen. Historische 1.000 Prognosen bleiben neben 950 neuen erhalten. Alle veröffentlichten Ports sind standardmäßig lokal gebunden, weil Authentifizierung, TLS und Rate Limits noch fehlen.

## Zehn typische technische Rückfragen

### 1. Warum drei Datenbanken?

PostgreSQL schützt strukturierte Fakten und Ergebnisse, MongoDB speichert verschachtelte Rohsensoren und Neo4j beantwortet Beziehungs- und Pfadfragen.

### 2. Liest Spark direkt aus MongoDB?

Spark liest einen kontrollierten Batch-Export der aktiven MongoDB-Collection. Der Export wird gezählt, nach `reading_id` sortiert, auf fehlende und doppelte IDs geprüft und erst dann atomar veröffentlicht. Ein Spark-Mongo-Connector ist für diese lokale Referenz bewusst nicht nötig.

### 3. Liest FastAPI die Datenbanken direkt?

Ja. Maschinen, Metriken, Prognosen und Pipeline-Läufe kommen aus PostgreSQL. Technische Abhängigkeiten kommen aus Neo4j. MongoDB bleibt Batch-Sensorquelle und ist kein API-Serving-System.

### 4. Warum werden nur 994.905 Messungen akzeptiert?

Der Generator injiziert kontrollierte Qualitätsfehler: 1.757 fehlende Temperaturen, 1.693 Temperatur-Bereichsverletzungen und 1.645 unbekannte Maschinenreferenzen. Sie werden mit Reason Code quarantänisiert.

### 5. Wie verhindern die Gates fehlerhafte Ergebnisse?

Das Source Gate blockiert Spark bei unvollständigen oder inkonsistenten Quellen. Das Feature Gate blockiert Metrik, ML und PostgreSQL-Persistenz bei Schemafehlern, fehlenden Maschinen, Nullschlüsseln, nur einer Klasse oder überlappenden Splits.

### 6. Wie wird Data Leakage verhindert?

Historische Fenster enden am Vortag. `future_*` und `risk_rank` sind keine Klassifikationsfeatures. Zwischen Training, Validierung und Test liegt jeweils ein Purge-Tag.

### 7. Warum ist Accuracy nicht die Leitmetrik?

Im Test sind 76 Prozent der Zeilen positiv. Eine reine Positive-Vorhersage erreicht 0,760 Accuracy, erkennt aber keinen negativen Fall. Deshalb werden Macro-F1 und Balanced Accuracy priorisiert.

### 8. Ist das Modell produktionsreif?

Nein. Balanced Accuracy 0,537 und Recall 0,180 für Klasse 0 zeigen nur schwache Trennung. Daten und Labels stammen vollständig aus einer Simulation.

### 9. Was wurde wirklich ausgeführt?

Der Full-Lauf `hardening_full_20261019T1028Z` verarbeitete eine Million Messungen; alle 13 Tasks endeten erfolgreich. 32 automatisierte Tests einschließlich vier realer Datenbankintegrationstests bestanden. Ein Host-PySpark-Test wurde mangels PySpark übersprungen; der zugehörige Pfad lief im Full-DAG.

### 10. Was fehlt vor externer Nutzung?

Authentifizierung, Rollen, TLS, Rate Limits, externer Secret Store, Monitoring, SLOs, Modellregistry, Drift-Erkennung sowie Backup-/Restore- und Recovery-Nachweise.
