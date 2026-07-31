"""Apply the new tables for the multi-agent architecture."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import psycopg2

url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

ddl = """
CREATE TABLE IF NOT EXISTS project_risk_profiles (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL UNIQUE REFERENCES projects(id),
    team_size           INTEGER,
    tech_debt_index     NUMERIC(4,3) DEFAULT 0.5,
    risk_tolerance      VARCHAR(20) DEFAULT 'medium',
    deployment_env      VARCHAR(50),
    notes               TEXT,
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS category_weight_history (
    id              BIGSERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    category        VARCHAR(50) NOT NULL,
    old_weight      NUMERIC(6,4) NOT NULL,
    new_weight      NUMERIC(6,4) NOT NULL,
    source          VARCHAR(50) DEFAULT 'manual',
    reason          TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weight_history_project_time
    ON category_weight_history(project_id, created_at);

CREATE TABLE IF NOT EXISTS metric_dependency_graph (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    source_metric_key   VARCHAR(100) NOT NULL,
    target_metric_key   VARCHAR(100) NOT NULL,
    lag_periods         INTEGER DEFAULT 0,
    correlation         NUMERIC(6,4) NOT NULL,
    sample_size         INTEGER NOT NULL,
    confidence          VARCHAR(50) NOT NULL,
    reason              TEXT,
    discovered_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dependency_graph_project_time
    ON metric_dependency_graph(project_id, discovered_at);
"""

cur.execute(ddl)
print("Migration applied successfully.")

# --- Extend recommendation_feedback with analytics columns ---
feedback_columns = [
    ("project_id",      "INTEGER REFERENCES projects(id)"),
    ("metric_id",       "INTEGER REFERENCES metric_definitions(id)"),
    ("metric_name",     "VARCHAR(255)"),
    ("category",        "VARCHAR(50)"),
    ("actual_value",    "NUMERIC"),
    ("target_value",    "NUMERIC"),
    ("deviation",       "NUMERIC"),
    ("severity",        "NUMERIC"),
    ("priority_score",  "NUMERIC"),
    ("user_role",       "VARCHAR(100)"),
    ("feedback_at",     "TIMESTAMP"),
]
for col_name, col_type in feedback_columns:
    cur.execute(f"""
        ALTER TABLE recommendation_feedback
        ADD COLUMN IF NOT EXISTS {col_name} {col_type};
    """)
print("recommendation_feedback columns extended.")

# Helpful index for analytics queries
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_feedback_analytics
        ON recommendation_feedback(project_id, category, feedback_at);
""")
print("Analytics index created.")

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
print("Tables in DB:", tables)

cur.close()
conn.close()
