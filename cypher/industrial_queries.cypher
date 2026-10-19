// 1. Components and shared dependencies of a high-risk machine
MATCH (m:Machine {machine_id: $machine_id})-[:HAS_COMPONENT]->(c:Component)-[:DEPENDS_ON]->(shared:Component)
OPTIONAL MATCH (other:Machine)-[:HAS_COMPONENT]->(:Component)-[:DEPENDS_ON]->(shared)
WHERE other <> m
RETURN m.machine_id, c.component_id, shared.component_id, collect(DISTINCT other.machine_id) AS affected_machines;

// 2. Short dependency paths between two machines
MATCH path = shortestPath((a:Machine {machine_id:$from})-[*..6]-(b:Machine {machine_id:$to}))
RETURN [node IN nodes(path) | coalesce(node.machine_id,node.component_id,node.line_id)] AS path_nodes, length(path) AS hops;

// 3. Maintenance tasks by component type
MATCH (m:Machine)-[:HAS_COMPONENT]->(c:Component)
OPTIONAL MATCH (m)-[:REQUIRES_MAINTENANCE]->(t:MaintenanceTask)
RETURN c.component_type, count(DISTINCT m) AS machines, count(DISTINCT t) AS tasks
ORDER BY tasks DESC, machines DESC;

