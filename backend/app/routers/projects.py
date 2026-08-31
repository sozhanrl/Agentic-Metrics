from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.connectors import github_connector
from app.routers.recommendations import generate_recommendations_for_project

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/from-github", response_model=schemas.GithubImportResponse)
async def create_project_from_github(
    payload: schemas.GithubImportRequest,
    db: Session = Depends(get_db),
):
    """
    Import real metric data directly from a GitHub repository.

    Strict Non-Randomness Contract:
    1. Parses and validates owner/repo from payload.repo_url.
    2. Looks up or creates a single Project row: source="github", external_id=f"{owner}/{repo}".
    3. Fetches live data via GitHub REST API (no synthetic jitter, no fallback to demo/seed data).
    4. Persists real MetricValue rows tagged with raw_payload.
    5. Runs the full multi-agent pipeline and returns enriched recommendations.
    6. Omitted/unverifiable metrics are explicitly returned in skipped_metrics.
    """
    owner, repo = github_connector.parse_github_url(payload.repo_url)

    # Idempotent lookup or creation of project row
    project = crud.get_or_create_github_project(db, owner, repo)

    # Ingest metrics from GitHub API
    samples_by_metric, skipped_metrics = await github_connector.fetch_repo_metrics(
        owner=owner,
        repo=repo,
        token=payload.token,
    )

    # Persist MetricValue rows for each verified metric sample
    definitions = {d.key: d for d in crud.get_metric_definitions(db)}
    for metric_key, samples in samples_by_metric.items():
        defn = definitions.get(metric_key)
        if not defn:
            continue
        for sample in samples:
            db_value = schemas.MetricValueCreate(
                project_id=project.id,
                metric_id=defn.id,
                value=sample.value,
                recorded_at=sample.recorded_at,
                raw_payload=sample.raw_payload,
            )
            crud.create_metric_value(db, db_value)

    # Run multi-agent pipeline against freshly persisted rows
    recommendations = []
    if samples_by_metric:
        recommendations = generate_recommendations_for_project(db, project.id)

    return schemas.GithubImportResponse(
        id=project.id,
        name=project.name,
        source=project.source,
        external_id=project.external_id,
        created_at=project.created_at,
        recommendations=recommendations,
        ingested_metrics=list(samples_by_metric.keys()),
        skipped_metrics=skipped_metrics,
    )



@router.get("", response_model=list[schemas.ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return crud.get_projects(db)


@router.post("", response_model=schemas.ProjectResponse)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    return crud.create_project(db, project)



@router.get("/{project_id}", response_model=schemas.ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ---------------------------------------------------------------------------
# Risk Profile endpoints (used by the Adaptive Weighting Engine — Idea #3)
# ---------------------------------------------------------------------------

@router.put("/{project_id}/risk-profile", response_model=schemas.RiskProfileResponse)
def upsert_risk_profile(
    project_id: int,
    data: schemas.RiskProfileCreate,
    db: Session = Depends(get_db),
):
    """
    Create or update the risk profile for a project.

    The risk profile feeds the Adaptive Weighting Engine, which adjusts
    category weights based on tech_debt_index, risk_tolerance, and team_size
    before each recommendation pipeline run.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.upsert_risk_profile(db, project_id, data)


@router.get("/{project_id}/risk-profile", response_model=schemas.RiskProfileResponse)
def get_risk_profile(project_id: int, db: Session = Depends(get_db)):
    """
    Retrieve the current risk profile for a project.
    Returns 404 if no profile has been set yet.
    """
    profile = crud.get_risk_profile(db, project_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=(
                "No risk profile set for this project. "
                "Use PUT /projects/{project_id}/risk-profile to create one."
            ),
        )
    return profile

