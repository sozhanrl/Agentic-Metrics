from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/projects", tags=["Projects"])


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

