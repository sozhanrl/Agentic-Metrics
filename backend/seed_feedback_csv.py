"""
seed_feedback_csv.py
--------------------
One-shot script to import data/feedback_seed.csv into the recommendation_feedback table.

Run from the backend/ directory with the venv active:
    python seed_feedback_csv.py

Uses psycopg2 directly (same as migrate.py) to avoid Neon serverless connection
timeouts that can happen with long-lived SQLAlchemy sessions.

Strategy:
  1. Reads the CSV.
  2. Ensures projects 1-5 exist (upsert stubs).
  3. Batch-inserts ALL recommendation stubs in one statement.
  4. Batch-inserts all 500 feedback rows in one executemany call.
  5. Reports totals. Idempotent — safe to re-run.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

CSV_PATH = Path(__file__).parent / "data" / "feedback_seed.csv"

PROJECT_NAMES = {
    1: "Alpha Project",
    2: "Beta Initiative",
    3: "Gamma Platform",
    4: "Delta Service",
    5: "Epsilon App",
}


def parse_bool(val: str) -> bool:
    return val.strip().lower() == "true"


def parse_dt(val: str):
    val = val.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def seed():
    print(f"Reading {CSV_PATH} ...")
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  Found {len(rows)} rows.")

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
    conn.autocommit = False
    cur = conn.cursor()

    # ── 1. Upsert project stubs ───────────────────────────────────────────────
    print("Ensuring projects exist ...")
    for pid, name in PROJECT_NAMES.items():
        cur.execute("""
            INSERT INTO projects (id, name, source, external_id)
            VALUES (%s, %s, 'github', %s)
            ON CONFLICT (id) DO NOTHING
        """, (pid, name, f"ext-{pid}"))
    conn.commit()
    print(f"  {len(PROJECT_NAMES)} projects upserted.")

    # ── 2. Collect unique (rec_id, project_id) pairs from CSV ────────────────
    rec_pairs: dict[int, int] = {}
    for row in rows:
        rec_id  = int(row["recommendation_id"])
        proj_id = int(row["project_id"])
        rec_pairs[rec_id] = proj_id

    print(f"Batch-inserting {len(rec_pairs)} recommendation stubs ...")
    cur.executemany("""
        INSERT INTO recommendations (id, project_id, title, explanation, priority_score, status)
        VALUES (%s, %s, %s, 'Auto-created stub for CSV seed.', 30.0, 'open')
        ON CONFLICT (id) DO NOTHING
    """, [
        (rid, pid, f"Recommendation #{rid}")
        for rid, pid in rec_pairs.items()
    ])
    conn.commit()
    print(f"  Done.")

    # ── 3. Batch-insert feedback rows ─────────────────────────────────────────
    print("Batch-inserting feedback rows ...")
    feedback_params = []
    for row in rows:
        feedback_params.append((
            int(row["feedback_id"]),
            int(row["recommendation_id"]),
            parse_bool(row["was_helpful"]),
            int(row["project_id"]),
            row["metric"].strip(),
            row["category"].strip(),
            float(row["actual"]),
            float(row["target"]),
            float(row["deviation"]),
            float(row["severity"]),
            float(row["priority_score"]),
            row["user_role"].strip(),
            parse_dt(row["timestamp"]),
        ))

    cur.executemany("""
        INSERT INTO recommendation_feedback
            (id, recommendation_id, was_helpful, project_id,
             metric_name, category, actual_value, target_value,
             deviation, severity, priority_score, user_role, feedback_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, feedback_params)
    conn.commit()

    # ── 4. Verify ─────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM recommendation_feedback WHERE metric_name IS NOT NULL")
    total_in_db = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"\nSeed complete!")
    print(f"   Feedback rows in DB with analytics data: {total_in_db}")


if __name__ == "__main__":
    seed()
