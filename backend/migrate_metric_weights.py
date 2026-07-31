"""
Migration v3 — metric_weights table.
=====================================

What this does
--------------
Creates the metric_weights table for per-metric self-learning granularity.

Unlike category_weight_history (append-only audit ledger), metric_weights is
UPSERTED — it holds the CURRENT learning state for each (project, metric) pair:

    weight        NUMERIC(8,4)   - multiplicative adjustment atop category weight
    confidence    NUMERIC(5,4)   - 0..1, fraction of confidence_sample_target reached
    sample_count  NUMERIC(10,4)  - decay-weighted total feedback samples
    trend         VARCHAR(20)    - 'increasing' | 'decreasing' | 'stable'
    last_updated  TIMESTAMP      - when the self-learning engine last wrote this row

This migration is additive and idempotent.  It does NOT modify any existing
tables or data.

Run after migrate.py and migrate_dependency_v2.py.
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import psycopg2

url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

# --------------------------------------------------------------------------
# Step 1 -- Create metric_weights table (idempotent)
# --------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS metric_weights (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    metric_name     VARCHAR(255) NOT NULL,
    weight          NUMERIC(8, 4)  NOT NULL DEFAULT 1.0,
    confidence      NUMERIC(5, 4)  NOT NULL DEFAULT 0.0,
    sample_count    NUMERIC(10, 4) NOT NULL DEFAULT 0.0,
    trend           VARCHAR(20)    NOT NULL DEFAULT 'stable',
    last_updated    TIMESTAMP      NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, metric_name)
);
""")
print("[OK] metric_weights table ensured.")

# --------------------------------------------------------------------------
# Step 2 -- Index on project_id for fast per-project lookups
# --------------------------------------------------------------------------
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_metric_weights_project
    ON metric_weights(project_id);
""")
print("[OK] idx_metric_weights_project index ensured.")

# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------
cur.execute("""
SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_name = 'metric_weights'
ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print("\nmetric_weights column definitions:")
for col in cols:
    name, dtype, prec, scale, nullable = col
    type_str = f"{dtype}({prec},{scale})" if prec else dtype
    print(f"  {name:<20} {type_str:<22} nullable={nullable}")

cur.execute("""
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'metric_weights'
ORDER BY indexname;
""")
for name, defn in cur.fetchall():
    print(f"  index: {name}: {defn}")

cur.close()
conn.close()
print("\nMigration v3 complete.")
