-- 1. Machines with the most failures (JOIN, GROUP BY, HAVING)
SELECT m.machine_id, m.line_id, COUNT(e.event_id) AS failures
FROM machines m INNER JOIN normalized_machine_events e ON e.machine_id = m.machine_id
WHERE e.event_type = 'failure'
GROUP BY m.machine_id, m.line_id HAVING COUNT(e.event_id) > 0
ORDER BY failures DESC LIMIT 10;

-- 2. Average temperature by production line (LEFT JOIN)
SELECT l.line_id, AVG(d.avg_temperature_c) AS avg_temperature_c
FROM production_lines l LEFT JOIN machines m ON m.line_id = l.line_id
LEFT JOIN machine_daily_metrics d ON d.machine_id = m.machine_id
GROUP BY l.line_id ORDER BY l.line_id;

-- 3. Maintenance demand by line (CTE and subquery)
WITH maintenance_load AS (
  SELECT m.line_id, COUNT(r.maintenance_id) AS tasks, SUM(r.duration_minutes) AS minutes
  FROM machines m JOIN maintenance_records r ON r.machine_id = m.machine_id GROUP BY m.line_id
)
SELECT * FROM maintenance_load WHERE minutes > (SELECT AVG(minutes) FROM maintenance_load) ORDER BY minutes DESC;

-- 4. Anomalous operating behavior (window function)
SELECT machine_id, metric_date, anomaly_rate,
       AVG(anomaly_rate) OVER (PARTITION BY machine_id ORDER BY metric_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS moving_7d_rate,
       DENSE_RANK() OVER (PARTITION BY metric_date ORDER BY anomaly_rate DESC) AS daily_risk_rank
FROM machine_daily_metrics ORDER BY metric_date DESC, daily_risk_rank;

-- 5. Maintenance history and latest task per machine
SELECT machine_id, performed_at, maintenance_type, duration_minutes,
       ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY performed_at DESC) AS recency_rank
FROM maintenance_records ORDER BY machine_id, performed_at DESC;

-- CRUD course evidence (execute in a transaction during demonstrations)
INSERT INTO pipeline_runs(run_id, started_at, status, profile) VALUES ('demo-run', now(), 'running', 'small');
UPDATE pipeline_runs SET status = 'success', finished_at = now() WHERE run_id = 'demo-run';
DELETE FROM pipeline_runs WHERE run_id = 'demo-run';

-- Index verification example
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM normalized_machine_events WHERE machine_id = 'M-017' ORDER BY occurred_at DESC;

