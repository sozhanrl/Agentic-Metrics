"""
Migration v4 — Bayesian Beta-Bernoulli Engine, Causal Edges, Context Memory, and Goal Constraints.
=============================================================================================

What this does
--------------
1. Adds alpha, beta, alpha0, beta0, domain_context columns to metric_weights table (if missing).
2. Backfills alpha, beta, alpha0, beta0 based on current weight values.
3. Creates causal_edges table for self-evolving causal graph.
4. Creates context_memory table for context-specific learned priors and predictiveness.
5. Creates goal_constraints table for goal-constrained recommendation optimization.

This migration is additive and idempotent.
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import psycopg2

url = os.getenv("DATABASE_URL")
if not url:
    raise ValueError("DATABASE_URL is not set in .env")

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

# --------------------------------------------------------------------------
# Step 1 -- Add columns to metric_weights table
# --------------------------------------------------------------------------
cur.execute("""
ALTER TABLE metric_weights
    ADD COLUMN IF NOT EXISTS alpha NUMERIC(10, 4) DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS beta NUMERIC(10, 4) DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS alpha0 NUMERIC(10, 4) DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS beta0 NUMERIC(10, 4) DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS domain_context VARCHAR(50);
""")
print("[OK] metric_weights columns ensured.")

# Backfill existing rows if alpha was NULL or default 5.0 while weight was modified
cur.execute("""
UPDATE metric_weights
SET alpha = GREATEST(0.1, weight * 10.0),
    beta  = GREATEST(0.1, (2.0 - weight) * 5.0),
    alpha0 = GREATEST(0.1, weight * 10.0),
    beta0  = GREATEST(0.1, (2.0 - weight) * 5.0)
WHERE alpha = 5.0 AND beta = 5.0 AND weight != 1.0;
""")
print("[OK] metric_weights backfilled.")

# --------------------------------------------------------------------------
# Step 2 -- Create causal_edges table
# --------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS causal_edges (
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
CREATE INDEX IF NOT EXISTS idx_causal_edges_project ON causal_edges(project_id, is_active);
""")
print("[OK] causal_edges table & index ensured.")

# --------------------------------------------------------------------------
# Step 3 -- Create context_memory table
# --------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS context_memory (
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
CREATE INDEX IF NOT EXISTS idx_context_memory_key ON context_memory(context_key, metric_name);
""")
print("[OK] context_memory table & index ensured.")

# --------------------------------------------------------------------------
# Step 4 -- Create goal_constraints table
# --------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS goal_constraints (
    id               BIGSERIAL PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES projects(id),
    constraint_type  VARCHAR(50) NOT NULL,
    constraint_value NUMERIC(10, 4) NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_goal_constraints_project ON goal_constraints(project_id, is_active);
""")
print("[OK] goal_constraints table & index ensured.")

cur.close()
conn.close()
print("\nMigration v4 complete.")
