"""
Migration -- Add nullable `domain` column to project_risk_profiles table.
========================================================================

What this does
--------------
Adds `domain` VARCHAR(50) to `project_risk_profiles` table if it does not
already exist. Safe and idempotent.
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import psycopg2

url = os.getenv("DATABASE_URL")
if not url:
    print("[SKIP] DATABASE_URL not set in .env")
else:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    # Step 1 -- Ensure table exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS project_risk_profiles (
        id              SERIAL PRIMARY KEY,
        project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id),
        team_size       INTEGER,
        tech_debt_index NUMERIC(4, 3) DEFAULT 0.5,
        risk_tolerance  VARCHAR(20) DEFAULT 'medium',
        deployment_env  VARCHAR(50),
        domain          VARCHAR(50),
        notes           TEXT,
        updated_at      TIMESTAMP DEFAULT NOW()
    );
    """)
    print("[OK] project_risk_profiles table ensured.")

    # Step 2 -- Add domain column if not exists
    cur.execute("""
    ALTER TABLE project_risk_profiles
        ADD COLUMN IF NOT EXISTS domain VARCHAR(50);
    """)
    print("[OK] domain VARCHAR(50) column ensured on project_risk_profiles.")

    cur.close()
    conn.close()
    print("[OK] Migration migrate_add_domain complete.")
