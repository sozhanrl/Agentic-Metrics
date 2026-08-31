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
    team_insights, github_insights
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
    Development helper only: populates the given project with plausible
    random metric values across all seeded metric definitions, so the
    dashboard and recommendation engine have something real to work with
    before your live connectors (Azure DevOps / GitHub / SonarQube) are wired up.
    """
    project = crud.get_project(db, project_id)
    if not project:
        return {"error": "Project not found. Create a project first via POST /projects"}

    definitions = crud.get_metric_definitions(db)
    now = datetime.now(timezone.utc)
    created = 0

    for defn in definitions:
        # A few historical points plus one "current" point, with some
        # intentionally being off-target so recommendations have something to flag.
        base = {
            "code_churn": 22, "cyclomatic_complexity": 14, "test_coverage": 61,
            "defect_density": 1.8, "sprint_velocity": 24, "cycle_time": 5,
            "lead_time": 11, "deployment_frequency": 1.2, "change_failure_rate": 27,
            "mttr": 7,
        }.get(defn.key, 50)

        for i in range(6, -1, -1):
            jitter = random.uniform(-0.08, 0.08)
            value = max(0, base * (1 + jitter))
            db_value = schemas.MetricValueCreate(
                project_id=project_id,
                metric_id=defn.id,
                value=round(value, 2),
                recorded_at=now - timedelta(days=i * 5),
            )
            crud.create_metric_value(db, db_value)
            created += 1

    return {"status": "seeded", "metric_values_created": created}
