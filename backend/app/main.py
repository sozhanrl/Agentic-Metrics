import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.routers import projects, metrics, recommendations, feedback

app = FastAPI(
    title="Agentic AI-Based Software Metrics Prioritization and Recommendation System",
    version="2.0",
)

# Allow the local Vite dev server (and any origin during development) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(metrics.router)
app.include_router(recommendations.router)
app.include_router(feedback.router)


@app.get("/")
def home():
    return {"message": "Agentic AI-Based Software Metrics Prioritization and Recommendation System"}


@app.get("/health")
def health():
    return {"status": "running"}


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
