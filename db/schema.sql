-- ============================================================
-- Agentic Software Metrics Prioritization System - DB Schema
-- ============================================================

-- Projects being tracked (maps to an Azure DevOps project / GitHub repo)
CREATE TABLE projects (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    source          VARCHAR(50) NOT NULL,   -- 'azure_devops' | 'github' | 'sonarqube'
    external_id     VARCHAR(255) NOT NULL,  -- id/slug in the external system
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Metric definitions (the catalog of metrics we know how to collect)
CREATE TABLE metric_definitions (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(100) NOT NULL UNIQUE,   -- e.g. 'code_churn', 'velocity', 'defect_density'
    display_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(50) NOT NULL,   -- 'code_quality' | 'process' | 'devops'
    source          VARCHAR(50) NOT NULL,   -- which connector produces it
    unit            VARCHAR(50),            -- '%', 'count', 'days', etc.
    higher_is_better BOOLEAN DEFAULT TRUE,
    description     TEXT
);

-- Raw metric values over time (this is the "history" table)
CREATE TABLE metric_values (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    metric_id       INTEGER NOT NULL REFERENCES metric_definitions(id),
    value           NUMERIC NOT NULL,
    recorded_at     TIMESTAMP NOT NULL,     -- when the metric applies to (e.g. sprint end date)
    collected_at    TIMESTAMP DEFAULT NOW(),-- when we ingested it
    raw_payload     JSONB                   -- original API response, for debugging/audit
);

CREATE INDEX idx_metric_values_project_time ON metric_values(project_id, recorded_at);
CREATE INDEX idx_metric_values_metric ON metric_values(metric_id);

-- Agent-generated recommendations
CREATE TABLE recommendations (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    title           VARCHAR(255) NOT NULL,
    explanation     TEXT NOT NULL,          -- human-readable reasoning
    priority_score  NUMERIC NOT NULL,       -- computed by prioritization engine
    related_metrics INTEGER[],              -- array of metric_definitions.id involved
    status          VARCHAR(50) DEFAULT 'open', -- 'open' | 'acknowledged' | 'actioned' | 'dismissed'
    created_at      TIMESTAMP DEFAULT NOW(),
    resolved_at     TIMESTAMP
);

-- Feedback loop: did the user act on it, what happened
CREATE TABLE recommendation_feedback (
    id                  SERIAL PRIMARY KEY,
    recommendation_id   INTEGER NOT NULL REFERENCES recommendations(id),
    was_helpful         BOOLEAN,
    user_comment        TEXT,
    outcome_metric_id   INTEGER REFERENCES metric_definitions(id), -- did the target metric improve?
    outcome_delta       NUMERIC,   -- change in that metric after the recommendation
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Seed some common metric definitions to start with
INSERT INTO metric_definitions (key, display_name, category, source, unit, higher_is_better, description) VALUES
('code_churn', 'Code Churn', 'code_quality', 'github', '%', FALSE, 'Percentage of recently written code that is modified soon after'),
('cyclomatic_complexity', 'Cyclomatic Complexity', 'code_quality', 'sonarqube', 'count', FALSE, 'Number of independent paths through code'),
('test_coverage', 'Test Coverage', 'code_quality', 'sonarqube', '%', TRUE, 'Percentage of code covered by automated tests'),
('defect_density', 'Defect Density', 'code_quality', 'sonarqube', 'defects/kloc', FALSE, 'Bugs per thousand lines of code'),
('sprint_velocity', 'Sprint Velocity', 'process', 'azure_devops', 'story points', TRUE, 'Story points completed per sprint'),
('cycle_time', 'Cycle Time', 'process', 'azure_devops', 'days', FALSE, 'Time from work started to work done'),
('lead_time', 'Lead Time', 'process', 'azure_devops', 'days', FALSE, 'Time from request to delivery'),
('deployment_frequency', 'Deployment Frequency', 'devops', 'github', 'per week', TRUE, 'How often code is deployed to production'),
('change_failure_rate', 'Change Failure Rate', 'devops', 'github', '%', FALSE, 'Percentage of deployments causing a failure'),
('mttr', 'Mean Time to Recovery', 'devops', 'github', 'hours', FALSE, 'Average time to recover from a failure');
