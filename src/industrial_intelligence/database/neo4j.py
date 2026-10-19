"""Neo4j synchronization without raw time-series duplication."""

from __future__ import annotations

import csv
import os
from pathlib import Path


def sync_components(path: Path) -> int:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "change-me-neo4j")),
    )
    query = """
        UNWIND $rows AS row
        MERGE (m:Machine {machine_id: row.machine_id})
        MERGE (c:Component {component_id: row.component_id})
        SET c.component_type = row.component_type
        MERGE (u:Component {component_id: row.shared_dependency_id})
        SET u.component_type = 'shared_utility'
        MERGE (m)-[:HAS_COMPONENT]->(c)
        MERGE (c)-[:DEPENDS_ON]->(u)
    """
    rows: list[dict[str, str]] = []
    loaded = 0
    with path.open(encoding="utf-8") as handle, driver:
        for row in csv.DictReader(handle):
            rows.append(row)
            if len(rows) == 500:
                driver.execute_query(query, parameters_={"rows": rows})
                loaded += len(rows)
                rows.clear()
        if rows:
            driver.execute_query(query, parameters_={"rows": rows})
            loaded += len(rows)
    return loaded
