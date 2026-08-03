-- ============================================================
-- Agentic Software Metrics Prioritization System - DB Schema
-- ============================================================
--
-- Migration history
-- -----------------
-- v1 (initial)      : Core tables — projects, metric_definitions, metric_values,
--                     recommendations, recommendation_feedback, project_risk_profiles,
--                     category_weight_history.  Applied via migrate.py.
-- v2 (dependency)   : Added metric_dependency_graph table + composite index.
--                     Applied via migrate_dependency_v2.py.
-- v3 (metric_weights): Added metric_weights table for per-metric self-learning
--                     granularity with confidence, sample_count, and trend tracking.
--                     Applied via migrate_metric_weights.py.
--
-- This file is the CANONICAL single-source schema.  All tables and indexes are
-- documented here; running the migration scripts on a fresh DB produces the same
-- result as running this file directly.
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

-- Per-project context that the adaptive weighting engine uses to adjust category weights.
-- risk_tolerance: 'low' | 'medium' | 'high'  (low = boost devops/process weights)
-- tech_debt_index: 0.0 – 1.0 (high = boost code_quality weight)
CREATE TABLE project_risk_profiles (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL UNIQUE REFERENCES projects(id),
    team_size           INTEGER,                    -- head count; small teams weight process less
    tech_debt_index     NUMERIC(4,3) DEFAULT 0.5,   -- 0 = clean  1 = severe debt
    risk_tolerance      VARCHAR(20) DEFAULT 'medium',-- low | medium | high
    deployment_env      VARCHAR(50),                -- 'cloud' | 'on-prem' | 'hybrid'
    notes               TEXT,
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Append-only ledger of every weight update (manual or self-learning driven).
-- Enables auditing and gives the self-learning loop its own history to work with.
CREATE TABLE category_weight_history (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    category        VARCHAR(50) NOT NULL,           -- code_quality | process | devops
    old_weight      NUMERIC(6,4) NOT NULL,
    new_weight      NUMERIC(6,4) NOT NULL,
    source          VARCHAR(50) DEFAULT 'manual',   -- 'manual' | 'self_learning'
    reason          TEXT,                           -- human-readable explanation of why
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_weight_history_project_time ON category_weight_history(project_id, created_at);

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

-- ============================================================
-- v2: Metric Dependency Graph (added by migrate_dependency_v2.py)
-- ============================================================
-- Append-only audit ledger of discovered metric-to-metric dependency edges.
-- Each run of the Dependency Discovery engine appends new rows; existing rows
-- are never overwritten, preserving the full evolution of the learned graph.
CREATE TABLE metric_dependency_graph (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    source_metric_key   VARCHAR(100) NOT NULL,
    target_metric_key   VARCHAR(100) NOT NULL,
    lag_periods         INTEGER NOT NULL DEFAULT 0,  -- weeks X leads Y by this many periods
    correlation         NUMERIC(5, 4) NOT NULL,       -- Pearson r [-1, +1] rounded to 4dp
    sample_size         INTEGER NOT NULL,
    confidence          VARCHAR(20) NOT NULL,          -- 'high' | 'medium' | 'low'
    reason              TEXT,                          -- human-readable discovery rationale
    discovered_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Composite index: accelerates crud.get_latest_dependency_edges(), which filters
-- by project_id and needs the most-recent discovered_at per (source, target) pair.
CREATE INDEX idx_dependency_graph_project_target
    ON metric_dependency_graph(project_id, target_metric_key, discovered_at DESC);


-- ============================================================
-- v3: Per-Metric Weights (added by migrate_metric_weights.py)
-- ============================================================
-- Per-metric learning state maintained by the self-learning engine.
-- Unlike category_weight_history (append-only ledger), this table is UPSERTED —
-- it always holds the CURRENT learning state for each (project, metric) pair.
-- Full history is recoverable from the sequence of upserts in the audit log.
--
-- weight        : multiplicative adjustment applied on top of category weight
-- confidence    : 0–1, fraction of `confidence_sample_target` reached
--                 (distinguishes a weight from 500 samples vs. 10 samples)
-- sample_count  : total decay-weighted feedback samples seen for this metric
-- trend         : 'increasing' | 'decreasing' | 'stable' based on recent delta
-- last_updated  : when the self-learning engine last wrote this row
CREATE TABLE metric_weights (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    metric_name     VARCHAR(255) NOT NULL,             -- matches metric_definitions.key
    weight          NUMERIC(8, 4) NOT NULL DEFAULT 1.0,
    confidence      NUMERIC(5, 4) NOT NULL DEFAULT 0.0, -- 0.0 = uninformed, 1.0 = fully confident
    sample_count    NUMERIC(10, 4) NOT NULL DEFAULT 0.0, -- decay-weighted sample sum
    trend           VARCHAR(20) NOT NULL DEFAULT 'stable', -- 'increasing' | 'decreasing' | 'stable'
    alpha           NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    beta            NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    alpha0          NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    beta0           NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    domain_context  VARCHAR(50),
    last_updated    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, metric_name)
);

CREATE INDEX idx_metric_weights_project ON metric_weights(project_id);


-- ============================================================
-- v4: Bayesian Engine, Causal Edges, Context Memory, Goal Constraints
-- ============================================================
CREATE TABLE causal_edges (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    source_metric       VARCHAR(100) NOT NULL,
    target_metric       VARCHAR(100) NOT NULL,
    edge_strength       NUMERIC(6, 4) NOT NULL DEFAULT 0.5,
    causal_confidence   NUMERIC(6, 4) NOT NULL DEFAULT 0.0,
    effect_type         VARCHAR(20) NOT NULL DEFAULT 'unknown',
    evidence_type       VARCHAR(30) NOT NULL DEFAULT 'correlation',
    competing_hypotheses INTEGER NOT NULL DEFAULT 0,
    confirmations       INTEGER NOT NULL DEFAULT 0,
    refutations         INTEGER NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    last_validated_at   TIMESTAMP,
    evolution_log       TEXT
);
CREATE INDEX idx_causal_edges_project ON causal_edges(project_id, is_active);

CREATE TABLE context_memory (
    id                  BIGSERIAL PRIMARY KEY,
    context_key         VARCHAR(255) NOT NULL,
    metric_name         VARCHAR(255) NOT NULL,
    learned_alpha0      NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    learned_beta0       NUMERIC(10, 4) NOT NULL DEFAULT 5.0,
    predictiveness      NUMERIC(6, 4) NOT NULL DEFAULT 0.5,
    outcome_correlation NUMERIC(6, 4),
    project_count       INTEGER NOT NULL DEFAULT 0,
    avg_outcome         NUMERIC(8, 4),
    last_updated        TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_context_memory_key ON context_memory(context_key, metric_name);

CREATE TABLE goal_constraints (
    id               BIGSERIAL PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES projects(id),
    constraint_type  VARCHAR(50) NOT NULL,
    constraint_value NUMERIC(10, 4) NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_goal_constraints_project ON goal_constraints(project_id, is_active);


