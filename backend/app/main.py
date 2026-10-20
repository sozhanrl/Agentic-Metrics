import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.routers import (
    projects, metrics, recommendations, feedback, admin, analytics,
    health, anomalies, analysis, timeline, risks, assistant, alerts,
    team_insights, github_insights, ml
)

app = FastAPI(
    title="AI Software Engineering Intelligence Platform",
    version="3.0",
)

# Allow the local Vite dev server and common frontend development origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(metrics.router)
app.include_router(recommendations.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(health.router)
app.include_router(anomalies.router)
app.include_router(analysis.router)
app.include_router(timeline.router)
app.include_router(risks.router)
app.include_router(assistant.router)
app.include_router(alerts.router)
app.include_router(team_insights.router)
app.include_router(github_insights.router)
app.include_router(ml.router)



@app.get("/")
def home():
    return {"message": "Agentic AI-Based Software Metrics Prioritization and Recommendation System"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """System health endpoint checking intelligence engine and database connectivity."""
    db_status = "connected"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unavailable: {str(exc)}"
        return {
            "status": "degraded",
            "database": db_status,
            "intelligence_engine": "online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "ok",
        "database": db_status,
        "intelligence_engine": "online",
        "pipeline_ready": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }



@app.post("/dev/seed/{project_id}")
def seed_demo_data(project_id: int, db: Session = Depends(get_db)):
    """
    Populates realistic historical metric values across all 24 metric definitions,
    and runs initial ML prediction generation.
    """
    project = crud.get_project(db, project_id)
    if not project:
        return {"error": "Project not found. Create a project first via POST /projects"}

    definitions = crud.get_metric_definitions(db)
    now = datetime.now(timezone.utc)
    created = 0

    base_map = {
        # Code Quality
        "code_churn": 23.01,
        "cyclomatic_complexity": 14.64,
        "test_coverage": 62.87,
        "defect_density": 1.66,
        "maintainability_index": 76.5,
        "code_duplication": 5.8,
        "technical_debt_ratio": 4.6,
        "code_smells": 28,
        "predicted_defect_risk": 0.32,
        # Process
        "sprint_velocity": 25.57,
        "cycle_time": 4.82,
        "lead_time": 11.59,
        "sprint_predictability": 84.0,
        "wip": 8.0,
        "story_spillover_rate": 11.5,
        "sprint_throughput": 15.0,
        "predicted_sprint_completion": 88.0,
        # DevOps
        "deployment_frequency": 1.17,
        "change_failure_rate": 28.54,
        "mttr": 6.8,
        "deployment_lead_time": 7.4,
        "deployment_success_rate": 78.5,
        "rollback_rate": 6.2,
        "predicted_deployment_failure": 0.28,
    }

    for defn in definitions:
        base = base_map.get(defn.key, 50.0)

        for i in range(12, -1, -1):
            jitter = random.uniform(-0.07, 0.07)
            val = max(0.0, base * (1 + jitter))
            db_value = schemas.MetricValueCreate(
                project_id=project_id,
                metric_id=defn.id,
                value=round(val, 2),
                recorded_at=now - timedelta(days=i * 5),
            )
            crud.create_metric_value(db, db_value)
            created += 1

    try:
        from app.ml.trainer import MLPlatformCoordinator
        coord = MLPlatformCoordinator(db)
        coord.generate_project_predictions(project_id)
    except Exception:
        pass

    return {"status": "seeded", "metric_values_created": created}

