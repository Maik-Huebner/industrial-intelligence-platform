db = db.getSiblingDB("industrial");
db.createCollection("sensor_readings");
db.createCollection("pipeline_documents");
db.sensor_readings.createIndex({ reading_id: 1 }, { unique: true });
db.sensor_readings.createIndex({ machine_id: 1, timestamp: -1 });
db.sensor_readings.createIndex({ "context.scenario": 1, machine_id: 1 });

