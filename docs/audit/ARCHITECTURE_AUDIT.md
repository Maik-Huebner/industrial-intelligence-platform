# Architektur- und Datenintegritätsaudit

Stand: 19. Oktober 2026

## Urteil

Die dokumentierte End-to-End-Architektur entspricht dem implementierten Pfad. MongoDB ist die tatsächliche Sensorquelle von Spark, PostgreSQL liefert strukturierte API-Daten, Neo4j liefert Graphantworten, und Modellvorhersagen werden in PostgreSQL mit einer Version gespeichert. Die drei Datenbanken haben unterschiedliche, nachvollziehbare Verantwortlichkeiten. Es wurde keine tote Kernkomponente gefunden.

## Tatsächlicher Datenfluss

```text
deterministischer Generator
  ├─ CSV/JSON-Stammdaten ────────────────> PostgreSQL
  ├─ JSONL-Sensorik -> atomarer Import ──> MongoDB
  └─ Komponenten/Beziehungen ────────────> Neo4j
MongoDB -> sortierter Snapshot -> Python-Validierung + Quarantäne
          -> Source Gate -> Spark DataFrames/SQL/Joins/Windows/Aggregationen
          -> partitioniertes Parquet -> Feature Gate -> Spark MLlib
          -> versionierte Artefakte -> PostgreSQL
PostgreSQL + Neo4j -> FastAPI
Airflow orchestriert die 13 Schritte und persistiert den Laufstatus.
```

## Abhängigkeitsnachweis

| Frage | Implementierter Nachweis | Ausführungsnachweis | Urteil |
|---|---|---|---|
| Ist MongoDB wirkliche Spark-Quelle? | `database/mongodb.py` exportiert `sensor_readings` sortiert nach `reading_id`; der DAG übergibt diesen Snapshot an Validierung und Spark. | Source Gate meldete `source: mongodb`, 1.000.000 Eingabezeilen. | PASS |
| Ist der Export konsistent? | Collection wird zunächst temporär aufgebaut und atomar umbenannt; Export prüft Count und schreibt Metadaten. | Unit-Test des Snapshotpfads; Full- und Fresh-Lauf ohne Count-Drift. | PASS |
| Sind Dateien und DB synchron? | deterministische IDs/Seed, Quell- und Qualitätsmetadaten, Count-Gates. | Full: 1.000.000 = 994.905 + 5.095; Fresh: 10.000 = 9.943 + 57. | PASS |
| Kommen Maschinenmetriken aus PostgreSQL? | `database/postgres.py` fragt `machine_daily_metrics` parametrisiert ab. | 50 aktuelle Metriken, API-Antwort gegen DB geprüft. | PASS |
| Greift FastAPI direkt auf PostgreSQL zu? | Dependency und Repository-Funktionen in `api/main.py`/`database/postgres.py`. | `/machines` und `/pipeline-runs/latest` live mit HTTP 200. | PASS |
| Greift die Graph-API auf Neo4j zu? | `database/neo4j.py` nutzt parametrisierte Cypher-Traversierung. | `/machines/M-001/dependencies` live mit HTTP 200 und Graphdaten. | PASS |
| Sind Vorhersagen versioniert? | PK/Upsert enthält `model_version`; API filtert und sendet `X-Model-Version`. | 1.000 Zeilen `synthetic-v1`, 950 Zeilen `synthetic-v2-classification-benchmark`. | PASS |
| Ist die Herkunft nachvollziehbar? | Run-ID, Profil, Seed, Qualitätsreport, Modellversion, Zeitstempel und Pipeline-Run. | Reports und DB-Laufdatensätze gegengeprüft. | PASS mit Grenze |

Die Grenze bei der Lineage: Es gibt keine zentrale, unveränderliche Lineage-Datenbank oder Artefakt-Hashes für jede Zwischenstufe. Für das Ausbildungsprojekt reichen die vorhandenen Run-/Modellversionen und Reports; für regulierte Produktion wäre dies auszubauen.

## Datenintegrität

### Full-Profil

| Objekt | Verifizierter Wert |
|---|---:|
| Maschinen | 50 |
| Produktionsaufträge | 600 |
| Wartungen | 320 |
| Störungen | 180 |
| MongoDB-Sensordokumente | 1.000.000 |
| gültige Messungen | 994.905 |
| Quarantäne | 5.095 |
| Spark-Featurezeilen | 4.950 |
| Neo4j-Komponenten | 220 |
| Neo4j-Beziehungen | 400 |
| PostgreSQL-Prognosen, historisch | 1.950 |

Die Quarantäne ist vollständig erklärt: 1.757 fehlende Temperaturen, 1.693 Temperaturwerte außerhalb des erlaubten Bereichs und 1.645 unbekannte Maschinenkennungen. Die Summe entspricht 5.095. Es gab keine doppelten Tageskeys und keine Null-Maschinenreferenzen. Die 1.645 unbekannten Maschinen-IDs erklären, warum MongoDB 51 verschiedene IDs enthält, obwohl nur 50 gültige Maschinen existieren.

### Isolierter Fresh-Start

Ein Archiv des Audit-Commits wurde unter eigenem Compose-Projektnamen mit neuen Volumes gestartet. Um Portkonflikte zu vermeiden, hatte dieser temporäre Stack keine Host-Port-Publikation. Die bestehende Hauptumgebung und ihre Volumes wurden nicht gelöscht.

- MongoDB: 10.000 Dokumente; 9.943 gültig, 57 quarantänisiert.
- PostgreSQL: 50 Maschinen, 50 Tagesmetriken, 950 Prognosen, zwei Pipeline-Läufe.
- Neo4j: 50 Maschinen, 220 Komponenten.
- API-Health: `status=ok`, PostgreSQL erreichbar.
- Ein geplanter und ein manuell ausgelöster Small-DAG-Lauf: jeweils 13/13 Tasks erfolgreich.

Die temporären Audit-Container und ausschließlich deren Volumes wurden danach entfernt. Die Hauptumgebung wurde mit ihren vorhandenen Volumes wieder gesund gestartet.

## Doppelte Datenhaltung

Die vorhandene Mehrfachhaltung ist beabsichtigt:

- JSONL ist reproduzierbares Staging, MongoDB ist aktive Sensorquelle.
- Quarantäne und validierter Snapshot sind prüfbare Zwischenstände.
- Parquet ist das spaltenorientierte Spark-Ergebnis.
- PostgreSQL enthält nur strukturierte Fach- und Ergebnisdaten, nicht die Million Rohmessungen.
- Neo4j enthält nur den technischen Kontextgraphen, nicht die Zeitreihe.

Unbeabsichtigte Duplizierung wurde nicht gefunden. Wiederholte Läufe aktualisieren Tagesmetriken, Graphen und dieselbe Modellversion idempotent; unterschiedliche Modellversionen bleiben absichtlich historisch erhalten.

## Befunde

| Priorität | Befund | Bewertung/Maßnahme |
|---|---|---|
| P1, behoben | Das Regressionsziel `lead(1)` konnte früher über die 80/20-Grenze reichen. | Grenztag wird jetzt entfernt; Metadaten und Spark-Test ergänzen den Nachweis. |
| P2 | MongoDB-Zeitstempel sind ISO-Strings statt BSON Date. | Deterministisch parsebar und im aktuellen Export geprüft; vor zeitbasierten Mongo-Abfragen migrieren. |
| P2 | Lineage ist reportbasiert und nicht manipulationssicher. | Für Produktion Artefakt-Hashes, Katalog/Registry und unveränderliche Run-Metadaten ergänzen. |
| P3 | Historische Präsentations- und Baseline-Artefakte bleiben bewusst erhalten. | Dateinamen und Dokumentation unterscheiden aktuelle von historischen Ergebnissen. |

## Dokumentationsabgleich

`README.md`, die Dateien unter `docs/architecture/` und die finale Präsentation zeigen denselben Pfad: FastAPI liest PostgreSQL und Neo4j direkt; MongoDB ist die kontrollierte Spark-Quelle. Aussagen über direkte Spark-Mongo-Connector-Nutzung wurden nicht gemacht. Der Snapshot-Export ist bewusst gewählt, damit ein konsistenter, reproduzierbarer Eingabestand trainiert wird.
