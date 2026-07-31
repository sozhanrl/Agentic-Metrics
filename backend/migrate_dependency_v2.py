"""
Migration v2 -- Metric Dependency Graph: precision + index upgrade.
===================================================================

What this does
--------------
1.  Tightens  `correlation`  column to NUMERIC(5,4) as specified in the DDL
    (5 total digits, 4 decimal places -> values in [-9.9999 to 9.9999], which
    covers all valid Pearson r values +/- safe headroom).

    The column was previously NUMERIC(6,4) -- tightening is safe because the
    discovery algorithm always rounds to 4 decimal places and Pearson r is
    always in [-1, +1].

2.  Adds the composite index the user specified:
        (project_id, target_metric_key, discovered_at DESC)
    This directly accelerates `crud.get_latest_dependency_edges`, which
    queries by project_id and needs the most-recent discovered_at per
    (source, target) pair.

    The old index (project_id, discovered_at) is dropped after the new one
    is created to avoid index bloat.

3.  Ensures the `reason` TEXT column is present (idempotent ADD COLUMN IF
    NOT EXISTS -- safe to re-run).

This migration is additive and idempotent.  It does NOT drop or recreate
the table, so existing discovered edges are fully preserved.
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
# Step 1 -- Ensure the table exists (idempotent guard for fresh DBs)
# --------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS metric_dependency_graph (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    source_metric_key   VARCHAR(100) NOT NULL,
    target_metric_key   VARCHAR(100) NOT NULL,
    lag_periods         INTEGER NOT NULL DEFAULT 0,
    correlation         NUMERIC(5, 4) NOT NULL,
    sample_size         INTEGER NOT NULL,
    confidence          VARCHAR(20) NOT NULL,
    reason              TEXT,
    discovered_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
""")
print("[OK] metric_dependency_graph table ensured.")

# --------------------------------------------------------------------------
# Step 2 -- Tighten correlation precision to NUMERIC(5,4)
#           ALTER COLUMN TYPE is idempotent because altering to the same
#           type is a no-op on most PG versions; the USING cast is safe.
# --------------------------------------------------------------------------
cur.execute("""
ALTER TABLE metric_dependency_graph
    ALTER COLUMN correlation TYPE NUMERIC(5, 4)
    USING correlation::NUMERIC(5, 4);
""")
print("[OK] correlation column precision set to NUMERIC(5,4).")

# --------------------------------------------------------------------------
# Step 3 -- Ensure `reason` column exists (in case the DB was created before
#           the reason column was added to the original migrate.py)
# --------------------------------------------------------------------------
cur.execute("""
ALTER TABLE metric_dependency_graph
    ADD COLUMN IF NOT EXISTS reason TEXT;
""")
print("[OK] reason TEXT column ensured.")

# --------------------------------------------------------------------------
# Step 4 -- Add the precise composite index from the DDL spec
# --------------------------------------------------------------------------
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_dependency_graph_project_target
    ON metric_dependency_graph(project_id, target_metric_key, discovered_at DESC);
""")
print("[OK] Composite index (project_id, target_metric_key, discovered_at DESC) created.")

# --------------------------------------------------------------------------
# Step 5 -- Drop the old coarser index (project_id, discovered_at) now that
#           the better one exists.  Use IF EXISTS so re-runs are safe.
# --------------------------------------------------------------------------
cur.execute("""
DROP INDEX IF EXISTS idx_dependency_graph_project_time;
""")
print("[OK] Old index idx_dependency_graph_project_time dropped.")

# --------------------------------------------------------------------------
# Verification -- show current indexes on the table
# --------------------------------------------------------------------------
cur.execute("""
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'metric_dependency_graph'
ORDER BY indexname;
""")
rows = cur.fetchall()
print("\nCurrent indexes on metric_dependency_graph:")
for name, defn in rows:
    print(f"  {name}: {defn}")

# Show column types
cur.execute("""
SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_name = 'metric_dependency_graph'
ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print("\nColumn definitions:")
for col in cols:
    name, dtype, prec, scale, nullable = col
    type_str = f"{dtype}({prec},{scale})" if prec else dtype
    print(f"  {name:<25} {type_str:<20} nullable={nullable}")

cur.close()
conn.close()
print("\nMigration v2 complete.")
