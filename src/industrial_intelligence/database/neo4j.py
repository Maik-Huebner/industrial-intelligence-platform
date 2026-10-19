"""Neo4j synchronization without raw time-series duplication."""

from __future__ import annotations

import csv
import os
from pathlib import Path


class Neo4jUnavailable(RuntimeError):
    """Raised when a bounded graph read cannot be completed."""


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "change-me-neo4j")),
        connection_timeout=float(os.getenv("NEO4J_CONNECT_TIMEOUT_SECONDS", "5")),
    )


def sync_components(path: Path) -> int:
    driver = _driver()
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


def machine_dependencies(machine_id: str, limit: int = 100) -> dict[str, object] | None:
    """Return real component dependencies and machines sharing each dependency."""
    query = """
        MATCH (m:Machine {machine_id: $machine_id})
        OPTIONAL MATCH (m)-[:HAS_COMPONENT]->(component:Component)
        OPTIONAL MATCH (component)-[:DEPENDS_ON]->(dependency:Component)
        OPTIONAL MATCH (neighbor:Machine)-[:HAS_COMPONENT]->(:Component)-[:DEPENDS_ON]->(dependency)
        WITH m, component, dependency, collect(DISTINCT neighbor.machine_id) AS neighbor_ids
        RETURN component.component_id AS component_id,
               component.component_type AS component_type,
               dependency.component_id AS dependency_id,
               dependency.component_type AS dependency_type,
               [id IN neighbor_ids WHERE id IS NOT NULL AND id <> m.machine_id][0..25]
                   AS affected_neighbor_machines
        ORDER BY component_id, dependency_id
        LIMIT $limit
    """
    driver = _driver()
    try:
        with driver:
            records, _, _ = driver.execute_query(
                query,
                parameters_={"machine_id": machine_id, "limit": limit},
            )
    except Exception as exc:
        raise Neo4jUnavailable("Neo4j dependency query failed") from exc
    if not records:
        return None
    dependencies = []
    for record in records:
        if record["component_id"] is None:
            continue
        dependencies.append(
            {
                "component_id": record["component_id"],
                "component_type": record["component_type"],
                "dependency_id": record["dependency_id"],
                "dependency_type": record["dependency_type"],
                "affected_neighbor_machines": list(record["affected_neighbor_machines"] or []),
                "relationship": "component DEPENDS_ON shared technical utility",
            }
        )
    return {"machine_id": machine_id, "dependencies": dependencies}
