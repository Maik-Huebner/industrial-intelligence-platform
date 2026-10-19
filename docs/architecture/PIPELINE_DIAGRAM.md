# Pipeline-Diagramm

## End-to-End-Architektur

```mermaid
flowchart LR
    U[Instandhaltung / Nutzer]
    CFG[Environment + Profil + Seed]
    GEN[Python IndustrialDataGenerator]

    subgraph STAGE[Dateibasiertes Staging und Arbeitsartefakte]
        CSV[Maschinen und Aufträge<br/>CSV]
        EVT[Wartung CSV<br/>Störungen JSON]
        SENS[Sensoren JSONL<br/>1.000.000 Dokumente]
        GRAPH[Komponenten CSV<br/>200 Zeilen]
        VALID[Validierte Sensor-CSV<br/>994.905 Zeilen]
        QUAR[Quarantäne JSONL<br/>5.095 Zeilen]
        PQ[Parquet Features<br/>4.950 Maschinen-Tage]
        PRED[Spark JSON-Prognosen<br/>950 Zeilen]
        REPORT[Reports und Modellartefakte]
    end

    PG[(PostgreSQL<br/>Stamm, Events, Metriken,<br/>versionierte Prognosen)]
    MO[(MongoDB<br/>Rohsensordokumente)]
    NEO[(Neo4j<br/>50 Machines, 220 Components,<br/>400 Beziehungen)]
    PYQ[Python-Validierung<br/>und lokale Baseline]
    SPARK[Apache Spark<br/>DataFrames, SQL, Joins,<br/>Windows, Aggregationen]
    ML[Spark MLlib<br/>Klassifikation, Regression,<br/>KMeans]
    API[FastAPI<br/>dateibasiertes Read API]
    AF[Apache Airflow<br/>Orchestrator, 10 Tasks]

    CFG -->|Profil full, Seed 20261019| GEN
    GEN -->|Maschinenstammdaten| CSV
    GEN -->|Wartungen und Störungen| EVT
    GEN -->|verschachtelte Sensordokumente| SENS
    GEN -->|Komponenten und Utilities| GRAPH

    CSV -->|Upserts| PG
    EVT -->|normalisierte Events und Wartungen| PG
    SENS -->|ReplaceOne Upserts| MO
    GRAPH -->|Cypher MERGE| NEO

    SENS -->|JSONL| PYQ
    CSV -->|gültige Maschinen-IDs| PYQ
    PYQ -->|gültige Zeilen| VALID
    PYQ -->|Reason Codes + Originaldokument| QUAR
    VALID -->|gesamte Historie| PYQ
    PYQ -->|50 lokale Maschinenmetriken| PG

    SENS -->|rohe JSONL, eigener Filterpfad| SPARK
    CSV -->|Maschinenkontext| SPARK
    EVT -->|Wartungs- und Störungskontext| SPARK
    SPARK -->|partitionierte Featuredaten| PQ
    PQ -->|Train, Validation, Test| ML
    ML -->|Testvorhersagen| PRED
    ML -->|Metriken und Modelle| REPORT
    PRED -->|Upsert mit Modellversion| PG

    CSV -->|Maschinenliste| API
    PYQ -->|machine_metrics.csv und predictions.json| API
    PRED -->|bevorzugte MLlib-Ausgabe| API
    REPORT -->|latest_pipeline_run.json| API
    API -->|REST-Responses| U

    AF -. startet und überwacht .-> GEN
    AF -. startet und überwacht .-> PYQ
    AF -. spark-submit .-> SPARK
    AF -. spark-submit .-> ML
    AF -. persistiert .-> PG
    AF -. synchronisiert .-> NEO

    NEO -->|separate Cypher-Abfragen| U
```

## Leseregeln

- Durchgezogene Pfeile zeigen tatsächlichen Datenfluss.
- Gestrichelte Pfeile zeigen Steuerung oder eine bewusst getrennte Nutzung.
- Airflow ist kein Speicher.
- MLlib ist Teil der Verarbeitung und keine Datenquelle.
- Neo4j liegt außerhalb des Vorhersagepfads.
- FastAPI liest im aktuellen Stand Dateien. Die PostgreSQL-Persistenz der Prognosen wird nicht für die API-Antwort verwendet.
