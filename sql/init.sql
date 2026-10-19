CREATE DATABASE airflow;

CREATE TABLE IF NOT EXISTS factories (
    factory_id text PRIMARY KEY,
    name text NOT NULL UNIQUE,
    timezone text NOT NULL DEFAULT 'Europe/Berlin'
);

CREATE TABLE IF NOT EXISTS production_lines (
    line_id text PRIMARY KEY,
    factory_id text NOT NULL REFERENCES factories(factory_id),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS machine_types (
    machine_type text PRIMARY KEY,
    description text NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    machine_id text PRIMARY KEY,
    line_id text NOT NULL REFERENCES production_lines(line_id),
    machine_type text NOT NULL REFERENCES machine_types(machine_type),
    installed_year integer NOT NULL CHECK (installed_year BETWEEN 1980 AND 2100),
    criticality smallint NOT NULL CHECK (criticality BETWEEN 1 AND 5),
    manufacturer text NOT NULL
);

CREATE TABLE IF NOT EXISTS production_orders (
    order_id text PRIMARY KEY,
    line_id text NOT NULL REFERENCES production_lines(line_id),
    product_code text NOT NULL,
    planned_units integer NOT NULL CHECK (planned_units > 0),
    started_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS maintenance_records (
    maintenance_id text PRIMARY KEY,
    machine_id text NOT NULL REFERENCES machines(machine_id),
    performed_at timestamptz NOT NULL,
    maintenance_type text NOT NULL,
    duration_minutes integer NOT NULL CHECK (duration_minutes >= 0),
    notes text
);

CREATE TABLE IF NOT EXISTS normalized_machine_events (
    event_id text PRIMARY KEY,
    machine_id text NOT NULL REFERENCES machines(machine_id),
    occurred_at timestamptz NOT NULL,
    event_type text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS machine_daily_metrics (
    machine_id text NOT NULL REFERENCES machines(machine_id),
    metric_date date NOT NULL,
    measurement_count bigint NOT NULL CHECK (measurement_count >= 0),
    avg_temperature_c double precision,
    max_temperature_c double precision,
    avg_vibration_mm_s double precision,
    avg_load_pct double precision,
    anomaly_rate double precision CHECK (anomaly_rate BETWEEN 0 AND 1),
    failure_count integer NOT NULL DEFAULT 0,
    maintenance_count integer NOT NULL DEFAULT 0,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (machine_id, metric_date)
);

CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id bigserial PRIMARY KEY,
    machine_id text NOT NULL REFERENCES machines(machine_id),
    prediction_date date NOT NULL,
    model_name text NOT NULL,
    model_version text NOT NULL,
    risk_probability double precision CHECK (risk_probability BETWEEN 0 AND 1),
    predicted_label integer CHECK (predicted_label IN (0, 1)),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (machine_id, prediction_date, model_name, model_version)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id text PRIMARY KEY,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    profile text NOT NULL CHECK (profile IN ('small', 'medium', 'full')),
    input_rows bigint,
    valid_rows bigint,
    rejected_rows bigint,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_metrics_date ON machine_daily_metrics(metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_events_machine_time ON normalized_machine_events(machine_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_machine_time ON maintenance_records(machine_id, performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_risk ON ml_predictions(prediction_date DESC, risk_probability DESC);

CREATE OR REPLACE VIEW machine_risk_overview AS
SELECT m.machine_id, m.line_id, m.machine_type, d.metric_date,
       d.avg_temperature_c, d.avg_vibration_mm_s, d.anomaly_rate,
       p.risk_probability, p.predicted_label
FROM machines m
LEFT JOIN machine_daily_metrics d ON d.machine_id = m.machine_id
LEFT JOIN ml_predictions p ON p.machine_id = m.machine_id AND p.prediction_date = d.metric_date;

INSERT INTO factories(factory_id, name) VALUES ('FACTORY-01', 'Demo Werk') ON CONFLICT DO NOTHING;
INSERT INTO production_lines(line_id, factory_id, name)
SELECT 'LINE-' || to_char(i, 'FM00'), 'FACTORY-01', 'Produktionslinie ' || i FROM generate_series(1,5) i
ON CONFLICT DO NOTHING;
INSERT INTO machine_types(machine_type, description) VALUES
('CNC','CNC machining center'), ('PRESS','Industrial press'), ('PUMP','Process pump'),
('ROBOT','Industrial robot'), ('CONVEYOR','Conveyor system') ON CONFLICT DO NOTHING;

