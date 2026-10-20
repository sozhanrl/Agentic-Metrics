"""
migrate_ml_intelligence.py
---------------------------
Database migration script to:
1. Seed new metric definitions for Code Quality, Process, and DevOps.
2. Create ML intelligence tables:
   - ml_model_registry
   - ml_training_runs
   - ml_predictions
   - ml_code_modules
   - ml_drift_status
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

NEW_METRICS = [
    # Code Quality
    ("maintainability_index", "Maintainability Index", "code_quality", "sonarqube", "score", True, "Holistic index (0-100) indicating ease of code maintenance"),
    ("code_duplication", "Code Duplication Percentage", "code_quality", "sonarqube", "%", False, "Percentage of duplicate code blocks across codebase"),
    ("technical_debt_ratio", "Technical Debt Ratio", "code_quality", "sonarqube", "%", False, "Ratio of remediation effort to total development effort"),
    ("code_smells", "Code Smell Count", "code_quality", "sonarqube", "count", False, "Count of maintainability and architectural code smells"),
    ("predicted_defect_risk", "Predicted Defect Risk", "code_quality", "ml_engine", "prob", False, "ML-predicted probability of post-release defects"),
    # Process
    ("sprint_predictability", "Sprint Predictability", "process", "azure_devops", "%", True, "Ratio of completed story points to committed story points"),
    ("wip", "Work in Progress (WIP)", "process", "azure_devops", "tasks", False, "Active concurrent work items in progress"),
    ("story_spillover_rate", "Story Spillover Rate", "process", "azure_devops", "%", False, "Percentage of sprint commitments that spill over to next sprint"),
    ("sprint_throughput", "Sprint Throughput", "process", "azure_devops", "stories/sprint", True, "Total number of completed work items per sprint cycle"),
    ("predicted_sprint_completion", "Predicted Sprint Completion", "process", "ml_engine", "%", True, "ML-predicted sprint scope completion probability"),
    # DevOps
    ("deployment_lead_time", "Deployment Lead Time", "devops", "github", "hours", False, "Time from commit to successful production deployment"),
    ("deployment_success_rate", "Deployment Success Rate", "devops", "github", "%", True, "Percentage of automated production deployments succeeding without incident"),
    ("rollback_rate", "Rollback Rate", "devops", "github", "%", False, "Percentage of production releases requiring rollback or hotfix"),
    ("predicted_deployment_failure", "Predicted Deployment Failure Probability", "devops", "ml_engine", "prob", False, "ML-predicted risk score of deployment failure"),
]

DDL = """
-- 1. ML Model Registry
CREATE TABLE IF NOT EXISTS ml_model_registry (
    id                  SERIAL PRIMARY KEY,
    model_id            VARCHAR(100) UNIQUE NOT NULL,
    name                VARCHAR(255) NOT NULL,
    category            VARCHAR(50) NOT NULL,
    algorithm           VARCHAR(100) NOT NULL,
    target_metric       VARCHAR(100) NOT NULL,
    version             VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    status              VARCHAR(50) NOT NULL DEFAULT 'ready',
    hyperparameters     JSONB,
    features            JSONB,
    evaluation_metrics  JSONB,
    artifact_path       VARCHAR(255),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- 2. ML Training Runs
CREATE TABLE IF NOT EXISTS ml_training_runs (
    id                  BIGSERIAL PRIMARY KEY,
    model_id            VARCHAR(100) NOT NULL,
    project_id          INTEGER REFERENCES projects(id),
    status              VARCHAR(50) NOT NULL,
    train_samples       INTEGER NOT NULL DEFAULT 0,
    test_samples        INTEGER NOT NULL DEFAULT 0,
    metrics_json        JSONB,
    duration_ms         INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 3. ML Predictions
CREATE TABLE IF NOT EXISTS ml_predictions (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    model_id            VARCHAR(100) NOT NULL,
    category            VARCHAR(50) NOT NULL,
    target_metric       VARCHAR(100) NOT NULL,
    current_value       NUMERIC,
    predicted_value     NUMERIC NOT NULL,
    horizon             VARCHAR(50) DEFAULT 'next_cycle',
    lower_bound         NUMERIC,
    upper_bound         NUMERIC,
    confidence          NUMERIC DEFAULT 0.85,
    risk_level          VARCHAR(20) DEFAULT 'low',
    feature_contributions JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_project ON ml_predictions(project_id, target_metric, created_at);

-- 4. ML Code Modules
CREATE TABLE IF NOT EXISTS ml_code_modules (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    module_name         VARCHAR(255) NOT NULL,
    file_path           VARCHAR(500),
    churn_pct           NUMERIC DEFAULT 0,
    complexity          NUMERIC DEFAULT 0,
    coverage_pct        NUMERIC DEFAULT 0,
    code_smells         INTEGER DEFAULT 0,
    defect_risk_level   VARCHAR(20) DEFAULT 'low',
    defect_risk_prob    NUMERIC DEFAULT 0.0,
    top_contributor     VARCHAR(100),
    updated_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ml_code_modules_project ON ml_code_modules(project_id, defect_risk_level);

-- 5. ML Drift Status
CREATE TABLE IF NOT EXISTS ml_drift_status (
    id                  BIGSERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    metric_key          VARCHAR(100) NOT NULL,
    baseline_mean       NUMERIC NOT NULL,
    current_mean        NUMERIC NOT NULL,
    drift_detected      BOOLEAN DEFAULT FALSE,
    p_value             NUMERIC,
    drift_score         NUMERIC,
    status              VARCHAR(50) DEFAULT 'healthy',
    checked_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ml_drift_project ON ml_drift_status(project_id, checked_at);
"""

def run():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating ML Intelligence tables...")
    cur.execute(DDL)
    print("  ML tables created or verified.")

    print("Seeding new metric definitions...")
    for key, display, cat, src, unit, higher_better, desc in NEW_METRICS:
        cur.execute("""
            INSERT INTO metric_definitions (key, display_name, category, source, unit, higher_is_better, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                higher_is_better = EXCLUDED.higher_is_better,
                description = EXCLUDED.description;
        """, (key, display, cat, src, unit, higher_better, desc))
    print(f"  {len(NEW_METRICS)} metric definitions upserted.")

    cur.close()
    conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    run()
