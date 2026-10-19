# Pipeline-Diagramm

```mermaid
flowchart LR
    G[Deterministischer Generator] --> PG[(PostgreSQL<br/>Stamm- und Ereignisdaten)]
    G --> ML[MongoDB Loader<br/>temporäre Collection]
    ML -->|atomarer Rename| MO[(MongoDB<br/>1.000.000 Sensoren)]
    ML --> PD[(pipeline_documents<br/>Snapshot-Metadaten)]
    G --> F[Wartung, Störungen,<br/>Komponenten]

    MO --> EX[Batch-Export<br/>sortiert + SHA-256]
    EX --> Q[Python-Validierung<br/>+ Quarantäne]
    EX --> SG{Source-Gate}
    Q --> SG
    G --> SG

    SG -->|bestanden| SP[Spark DataFrames<br/>SQL · Joins · Windows]
    SP --> PQ[(Parquet Features<br/>4.950 Zeilen)]
    PQ --> FG{Feature-Gate}
    FG -->|bestanden| MLL[MLlib<br/>Klassifikation · Regression · KMeans]
    FG --> PM[Python-Metriken]

    MLL --> R[Reports, Modelle,<br/>950 Prognosen]
    R --> PG
    PM --> PG
    F --> N[(Neo4j<br/>Abhängigkeitsgraph)]

    PG --> API[FastAPI<br/>typisiert + paginiert]
    N --> API
    API --> U[Nutzer]

    AF[Airflow<br/>13 Tasks] -. orchestriert .-> G
    AF -. Gates .-> SG
    AF -. Gates .-> FG
    AF -. finale Konsistenz .-> PG
```

## Leseregeln

- MongoDB ist die Quellinstanz für Spark. Der JSONL-Export ist ein beobachteter Snapshot mit Manifest, kein unabhängiges Rohdatensystem.
- PostgreSQL ist die Serving-Quelle für Maschinen, Metriken, Prognosen und Pipeline-Läufe.
- Neo4j ist die Serving-Quelle für Komponentenabhängigkeiten. Der Graph fließt nicht in MLlib ein.
- Beide Gates liegen vor MLlib. Die finale Konsistenzprüfung liegt nach den Persistenzschritten und darf nur einen vollständig veröffentlichten Lauf als erfolgreich markieren.
