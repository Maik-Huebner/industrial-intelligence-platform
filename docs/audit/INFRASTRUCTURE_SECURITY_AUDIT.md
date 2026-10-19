# Infrastruktur- und Sicherheitsaudit

Stand: 19. Oktober 2026

## Ergebnis

Der Compose-Stack ist für eine lokale Ausbildungs- und Demo-Umgebung funktionsfähig. Dienste besitzen Healthchecks, persistente Volumes und ein internes Netzwerk; veröffentlichte Ports binden standardmäßig ausschließlich an `127.0.0.1`. Die Plattform ist ausdrücklich **nicht für einen direkt öffentlich erreichbaren Produktionsbetrieb abgesichert**.

## Komponentenprüfung

| Bereich | Tatsächlicher Befund | Status |
|---|---|---|
| Compose-Syntax | `docker compose config --quiet` erfolgreich | PASS |
| Images | PostgreSQL 16.4 Alpine, MongoDB 7.0.14 Jammy, Neo4j 5.23 Community, Spark 3.5.3, Airflow 2.10.2, Python-App | PASS |
| Healthchecks | PostgreSQL, MongoDB, Neo4j, Spark Master, Airflow Webserver und API vorhanden; Hauptstack gesund | PASS |
| Persistenz | benannte Volumes für PostgreSQL, MongoDB, Neo4j und Airflow-Logs; Projektartefakte als kontrollierte Bind-Mounts | PASS |
| Netzwerk | ein projektspezifisches Compose-Netz; DB-Hostports nur lokal | PASS |
| Startreihenfolge | `depends_on` mit Health-/Completion-Bedingungen | PASS |
| Restart | zentrale Langläufer besitzen definierte Restart-Policy | PASS |
| Umgebungsvariablen | `.env.example`, keine echte `.env` verfolgt; Variablen mit lokalen Beispielwerten | PASS mit Einschränkung |
| Secrets | keine realen Secrets in Git/History gefunden; Compose-Fallbacks lauten bewusst `change-me` | PASS für Veröffentlichung, FAIL für Produktion ohne Override |
| Privilegien | Airflow läuft als `airflow`; App-Image besitzt keine `USER`-Anweisung und läuft als root | PARTIAL |
| Host-Mounts | nur Projektpfade für DAGs, Daten, Modelle und Reports; kein Docker-Socket/Host-Root | PASS |
| API-Schutz | keine Authentifizierung, Autorisierung, TLS oder Rate Limits | FAIL für öffentliche Exposition |
| Logging | Docker-Logs und Airflow-Logs vorhanden | PASS lokal; zentrale Aggregation fehlt |
| Ressourcen | Spark/Airflow speicherbewusst konfiguriert; keine allgemeinen CPU-/RAM-Limits | PARTIAL |

## Realer Start- und Wiederanlaufnachweis

Die bestehende Full-Umgebung lief gesund und enthielt den erfolgreichen DAG `hardening_full_20261019T1028Z` mit 13/13 Tasks. Zusätzlich wurde aus dem Audit-Commit eine isolierte Umgebung mit eigenem Projektnamen und neuen Volumes erstellt. Ein anfänglicher zweiter gleichzeitiger Spark-Lauf wurde durch Host-Speicherdruck beendet. Nach kontrolliertem Stoppen — nicht Löschen — der Hauptcontainer liefen in der isolierten Umgebung sowohl der geplante als auch der manuelle Small-DAG vollständig durch. Das ist ein belastbarer Fresh-Start-Nachweis, aber kein Kapazitätsbenchmark für zwei parallele Cluster.

Nach dem Audit wurden ausschließlich die temporären Audit-Volumes entfernt. Die Hauptumgebung wurde mit ihren bestehenden Daten wieder gestartet und als gesund geprüft. Wegen lokaler Fremdcontainer werden dort konfliktfreie High Ports verwendet; die Containerports und der dokumentierte Standard bleiben unverändert.

## Airflow- und Qualitätsgates

- 13 explizite Tasks, `max_active_runs=1`, Retries und Execution Timeouts.
- Große Daten werden über Dateien/DBs übergeben; XCom enthält nur Metadaten.
- Source Gate stoppt unzulässige Fehlerquote, inkonsistente Counts oder Maschinenreferenzen vor Spark.
- Feature Gate stoppt fehlende Keys/Targets, leere Klassen oder inkonsistente Splits vor MLlib.
- Persistenz neuer Ergebnisse folgt den Gates; ein fehlgeschlagener Gate-Lauf wird damit nicht zur aktuellen Modellversion veröffentlicht.
- Unit-Tests decken gültige, tolerierbar fehlerhafte und kritische Qualitätsfälle ab. Idempotenz wurde durch wiederholte DAG-Läufe und konstante Zielcounts geprüft.

Ein echter Prozessabbruch wurde nicht in der Hauptumgebung erzwungen. Der ressourcenbedingte Retry des isolierten Transform-Tasks belegt den Wiederanlaufmechanismus ohne absichtlich Daten zu beschädigen.

## API-Audit

Live geprüft wurden `/health`, `/machines`, `/pipeline-runs/latest` und `/machines/M-001/dependencies`; alle lieferten HTTP 200 und tatsächliche PostgreSQL-/Neo4j-Daten. Die Implementierung verwendet Pydantic-Response-Modelle, validierte Pfad-/Queryparameter, begrenzte Pagination, parametrisierte SQL-/Cypher-Abfragen und definierte Fehlercodes. Modellversion und Seitendaten werden über Header beziehungsweise Antwortfelder nachvollziehbar gemacht.

Die Health-Antwort nennt korrekt `authentication: not_configured_local_only`. Dies ist kein produktionsfähiger Zugriffsschutz.

## Befunde nach Priorität

### P0

Keine.

### P1

Keine offenen Infrastruktur-P1. Der isolierte Fresh-Start und die Hauptumgebung sind funktionsfähig.

### P2

- API ohne AuthN/AuthZ, TLS-Terminierung und Rate Limiting; nur lokale Bindung verhindert derzeit externe Exposition.
- Standard-Fallbackpasswörter sind für den lokalen Quickstart geeignet, müssen in jeder geteilten Umgebung ersetzt werden.
- App-Container läuft als root. Vor Produktion einen festen unprivilegierten Benutzer und read-only root filesystem prüfen.
- Keine CVE-/SBOM-Prüfung im Audit: `pip-audit` beziehungsweise eine Offline-Vulnerability-Datenbank waren nicht vorhanden.
- Keine Backups, Restore-Probe, zentrale Logs, Metriken/Alerts oder SLOs.
- Image-Tags sind versioniert, aber nicht per Digest unveränderlich gepinnt.

### P3

- Ressourcengrenzen und Compose-Profile könnten für kleine Hosts weiter differenziert werden.
- Security Header und Request-ID-Middleware wären nützliche Härtungen.

## Mindestmaßnahmen vor externer Bereitstellung

1. Echte Secret-Verwaltung und Rotation; Start bei Defaultwerten verweigern.
2. Reverse Proxy/API-Gateway mit TLS, Authentifizierung, Autorisierung und Rate Limits.
3. Unprivilegierter App-Benutzer, reduzierte Linux-Capabilities und möglichst read-only Dateisystem.
4. Keine Datenbankports veröffentlichen; nur private Netze beziehungsweise Firewallregeln.
5. SBOM, signierte/digest-gepinnte Images und automatisierter CVE-Scan.
6. Backup-/Restore-Test, Monitoring, zentrale Logs, Alerts und definierte Betriebsziele.
7. Last-, Fehlertoleranz- und Recovery-Tests auf der Zielinfrastruktur.
