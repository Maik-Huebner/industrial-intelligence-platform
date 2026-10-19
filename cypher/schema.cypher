CREATE CONSTRAINT factory_id IF NOT EXISTS FOR (n:Factory) REQUIRE n.factory_id IS UNIQUE;
CREATE CONSTRAINT line_id IF NOT EXISTS FOR (n:ProductionLine) REQUIRE n.line_id IS UNIQUE;
CREATE CONSTRAINT machine_id IF NOT EXISTS FOR (n:Machine) REQUIRE n.machine_id IS UNIQUE;
CREATE CONSTRAINT component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.component_id IS UNIQUE;
CREATE CONSTRAINT sensor_id IF NOT EXISTS FOR (n:Sensor) REQUIRE n.sensor_id IS UNIQUE;
CREATE CONSTRAINT maintenance_id IF NOT EXISTS FOR (n:MaintenanceTask) REQUIRE n.maintenance_id IS UNIQUE;
CREATE INDEX component_type IF NOT EXISTS FOR (n:Component) ON (n.component_type);

MERGE (f:Factory {factory_id:'FACTORY-01'}) SET f.name = 'Demo Werk';
UNWIND range(1,5) AS i
MERGE (l:ProductionLine {line_id:'LINE-' + right('0' + toString(i),2)})
MERGE (f)-[:HAS_LINE]->(l);

