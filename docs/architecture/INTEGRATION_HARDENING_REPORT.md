# Integration Hardening Report

**Workorder:** Production Integration & Pipeline Hardening<br>
**Datum:** 19. Oktober 2026<br>
**Branch:** `feature/pipeline-integration-hardening`<br>
**Referenz-Run:** `hardening_full_20261019T1028Z`

## Ergebnis

Die lokale Plattform ist jetzt technisch durchgängig integriert. MongoDB ist die verifizierte Sensorquelle für Spark, zwei Quality Gates schützen ML und Ergebnis-Persistenz, FastAPI liest PostgreSQL und Neo4j direkt, und ein vollständiger Lauf mit 1.000.000 Messungen endete mit allen 13 Airflow-Tasks erfolgreich. Historische Modellresultate wurden erhalten.

Dieser Nachweis gilt für die lokale Referenzumgebung. Er ist keine Aussage über Produktionsfreigabe, industrielle Modellgüte oder öffentliche Exponierbarkeit.

## Architekturentscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Sensorquelle | MongoDB `sensor_readings` | Die operative Quelle ist nicht mehr nur eine parallele Kopie. |
| Spark-Anbindung | kontrollierter, sortierter JSONL-Batch-Export | reproduzierbar, speicherschonend und ohne zusätzliche Connector-Abhängigkeit |
| MongoDB-Load | temporäre Collection plus atomarer Rename | ein Teilausfall ersetzt nie den letzten vollständigen Snapshot |
| Source Gate | vor Spark | unvollständige oder inkonsistente Quellen dürfen keine Features erzeugen |
| Feature Gate | vor Metrik, ML und PostgreSQL-Persistenz | defekte Features dürfen keine Ergebnisse veröffentlichen |
| FastAPI | direkte Read-only-Abfragen gegen PostgreSQL und Neo4j | Datenbanken sind tatsächlich Teil des Serving-Pfads |
| Modellversion | expliziter Filter mit konfigurierbarer Default-Version | alte 1.000 Prognosen bleiben erhalten und abrufbar |
| Netzwerk | veröffentlichte Ports standardmäßig `127.0.0.1` | API besitzt noch keine Authentifizierung |

## MongoDB-Snapshot-Vertrag

Der Loader streamt die Generator-JSONL in Batches von 5.000 Dokumenten in eine eindeutige temporäre Collection. Ein Unique Index auf `reading_id` verhindert Duplikate. Erst nach vollständiger Zählprüfung wird die Collection atomar als `sensor_readings` aktiviert. Metadaten in `pipeline_documents` dokumentieren `records`, `source_sha256`, Batchgröße und Zeitpunkte.

Der Export liest die aktive Collection mit Cursor und Batchgröße 5.000, sortiert nach `reading_id`, entfernt `_id` und schreibt zunächst eine temporäre Datei. Veröffentlicht wird nur, wenn Quell- und Exportanzahl übereinstimmen und weder fehlende noch doppelte IDs gefunden wurden. Das Exportmanifest enthält SHA-256, Sortierung, Mengen und Zeitpunkte.

Gemessener Full-Export:

| Kennzahl | Wert |
|---|---:|
| MongoDB-Dokumente | 1.000.000 |
| Exportierte Dokumente | 1.000.000 |
| Fehlende IDs | 0 |
| Doppelte IDs | 0 |
| Batchgröße | 5.000 |
| manuell gemessene Exportdauer | 15,9 s |

## Quality Gates

### Source Gate

Das Gate vergleicht Generator-, Export- und Qualitätsmanifest. Es verlangt 50 Maschinenreferenzen, identische Quell-/Exportmengen, keine Export-Identitätsfehler und eine Ausschussquote von höchstens zwei Prozent.

Gemessen: 994.905 gültige und 5.095 abgewiesene Messungen, also 0,5095 Prozent Ausschuss. Die Quarantäne enthält 1.757 fehlende Temperaturen, 1.693 Bereichsverletzungen und 1.645 unbekannte Maschinenreferenzen.

### Feature Gate

Das Gate prüft erforderliche Spalten, Zeilen- und Maschinenabdeckung, Nullschlüssel, beide Zielklassen sowie die purged chronologischen Split-Grenzen.

| Split | Klasse 0 | Klasse 1 |
|---|---:|---:|
| Gesamt | 1.891 | 3.059 |
| Training | 1.342 | 1.608 |
| Validierung | 293 | 657 |
| Test | 228 | 722 |

Alle Splits enthalten beide Klassen. Train, Validierung und Test überlappen zeitlich nicht; nach Training und Validierung liegt jeweils ein Purge-Tag.

## FastAPI-Integration

Die API-Version `0.2.0` liefert Pydantic-validierte Antworten. PostgreSQL-Abfragen sind parametriert und mit Connect-/Statement-Timeouts begrenzt. Neo4j-Abfragen sind parametriert; Limits und zurückgegebene Nachbarlisten sind begrenzt. Interne Verbindungsfehler werden als generisches `503` abgebildet.

Verifizierte Endpunkte:

- `/health`
- `/machines`, `/machines/{machine_id}`, `/machines/{machine_id}/metrics`
- `/predictions`, `/predictions/{machine_id}`
- `/pipeline-runs`, `/pipeline-runs/latest`
- `/machines/{machine_id}/dependencies`

Listen liefern `X-Total-Count`, `X-Limit` und `X-Offset`; Prognosen zusätzlich `X-Model-Version`. Ohne expliziten Filter verwendet die API `synthetic-v2-classification-benchmark`. Ein realer Aufruf für `M-017` lieferte vier direkte Komponenten sowie neun Nachbarmaschinen über geteilte Linien-Utilities.

## Vollständiger Airflow-Lauf

| Task | Status | Dauer |
|---|---|---:|
| `validate_sources` | success | 0,10 s |
| `extract_industrial_data` | success | 29,58 s |
| `export_mongodb_snapshot` | success | 17,00 s |
| `validate_and_normalize` | success | 8,25 s |
| `enforce_source_quality_gate` | success | 0,09 s |
| `run_spark_transformation` | success | 45,87 s |
| `synchronize_neo4j_relationships` | success | 1,03 s |
| `enforce_feature_quality_gate` | success | 9,33 s |
| `calculate_machine_metrics` | success | 2,20 s |
| `run_mllib_training_and_inference` | success | 33,76 s |
| `persist_postgresql_results` | success | 0,22 s |
| `run_final_consistency_checks` | success | 0,16 s |
| `generate_pipeline_summary` | success | 0,12 s beim erfolgreichen Retry |

Die aktive Verarbeitung bis zum finalen Konsistenzcheck dauerte rund 2:33 Minuten. Die Summary-Task lief zunächst wegen eines falschen Airflow-Importpfads in einen Retry. Nach der Korrektur war der Retry erfolgreich; der DAG-Endzeitpunkt enthält zusätzlich den dreiminütigen Retry-Abstand. Diese Abweichung wird nicht als Laufzeitverbesserung beschönigt.

## Persistierter Endzustand

| System | Nachweis |
|---|---:|
| MongoDB `sensor_readings` | 1.000.000 |
| Spark-Features | 4.950 |
| PostgreSQL Maschinenmetriken | 50 |
| PostgreSQL `synthetic-v1` | 1.000 Prognosen |
| PostgreSQL `synthetic-v2-classification-benchmark` | 950 Prognosen |
| PostgreSQL gesamt | 1.950 Prognosen |
| Neo4j Komponenten | 220 |
| Neo4j Beziehungen | 400 |

## Tests und Artefakte

- 32 Tests bestanden, einschließlich vier realer Datenbankintegrationstests.
- Ein PySpark-Vertragstest wurde auf dem Host mangels PySpark übersprungen; die verwendete Spark-Normalisierung lief im Full-DAG erfolgreich.
- Compose-Konfiguration, DAG-Import, reale API-Aufrufe und vollständiger DAG wurden geprüft.
- Die bestehende Präsentation wurde als neue Datei aktualisiert; das Original blieb unverändert.

## Bewusst nicht gelöste Produktionsanforderungen

- Authentifizierung und Rollenmodell
- TLS-Terminierung und Rate Limiting
- externer Secret Store und Schlüsselrotation
- Modellregistry, Drift-, Datenqualitäts- und SLO-Monitoring
- Backup-/Restore-Übungen und Disaster-Recovery-Nachweis
- reale Historien und fachlich validierte Labels

Vor einer externen Exponierung müssen diese Punkte umgesetzt und separat abgenommen werden.
