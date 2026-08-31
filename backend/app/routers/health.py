"""
Health Router — AI Software Engineering Intelligence Platform.

Endpoints for computing, snapshotting, and querying project health scores.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.perceiver import perceive_all
from app.agents.health_scorer import compute_health_score
from app.agents.adaptive_weighter import compute_adaptive_weights
from app.agents.config import default_config

router = APIRouter(prefix="/projects", tags=["Health"])


@router.get("/{project_id}/health", response_model=schemas.HealthSnapshotResponse)
def get_project_health(project_id: int, db: Session = Depends(get_db)):
    """
    Compute current project health score and return snapshot with sub-scores,
    trend momentum, key drivers, strengths, and weaknesses.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        return schemas.HealthSnapshotResponse(
            project_id=project_id,
            overall_score=0.0,
            code_quality_score=0.0,
            process_score=0.0,
            devops_score=0.0,
            ai_risk_score=0.0,
            status_trend="stable",
            key_drivers=["No metric data available yet. Ingest telemetry to calculate health score."],
        )

    # History map for trend
    history_map = {}
    for _, definition in metric_rows:
        history = crud.get_metric_history(db, project_id, definition.id, limit=10)
        history_map[definition.id] = list(reversed(history))

    cfg = default_config()
    signals = perceive_all(metric_rows, history_map, cfg)

    # Adaptive weights & risk profile
    risk_profile = crud.get_risk_profile(db, project_id)
    base_weights = crud.get_latest_weights(db, project_id)
    adaptive_weights, _ = compute_adaptive_weights(base_weights=base_weights, risk_profile=risk_profile, cfg=cfg)

    # Recommendations & previous snapshot
    recommendations = crud.get_recommendations(db, project_id)
    previous_snapshot = crud.get_latest_health_snapshot(db, project_id)

    # Compute health score
    health_result = compute_health_score(
        signals=signals,
        recommendations=recommendations,
        previous_snapshot=previous_snapshot,
        adaptive_weights=adaptive_weights,
        cfg=cfg,
    )

    # Persist snapshot
    saved_snapshot = crud.create_health_snapshot(
        db=db,
        project_id=project_id,
        overall_score=health_result.overall_score,
        code_quality_score=health_result.code_quality_score,
        process_score=health_result.process_score,
        devops_score=health_result.devops_score,
        ai_risk_score=health_result.ai_risk_score,
        status_trend=health_result.status_trend,
    )

    return schemas.HealthSnapshotResponse(
        id=saved_snapshot.id,
        project_id=project_id,
        overall_score=health_result.overall_score,
        code_quality_score=health_result.code_quality_score,
        process_score=health_result.process_score,
        devops_score=health_result.devops_score,
        ai_risk_score=health_result.ai_risk_score,
        status_trend=health_result.status_trend,
        previous_score=health_result.previous_score,
        percentage_change=health_result.percentage_change,
        category_health=health_result.category_health,
        key_drivers=health_result.key_drivers,
        top_strengths=health_result.top_strengths,
        top_weaknesses=health_result.top_weaknesses,
        created_at=saved_snapshot.created_at,
    )


@router.get("/{project_id}/health/history", response_model=list[schemas.HealthSnapshotResponse])
def get_health_history(project_id: int, limit: int = 30, db: Session = Depends(get_db)):
    """
    Get historical health snapshots for trend charts.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    snapshots = crud.get_health_snapshots(db, project_id, limit=limit)
    return [
        schemas.HealthSnapshotResponse(
            id=s.id,
            project_id=s.project_id,
            overall_score=float(s.overall_score),
            code_quality_score=float(s.code_quality_score),
            process_score=float(s.process_score),
            devops_score=float(s.devops_score),
            ai_risk_score=float(s.ai_risk_score),
            status_trend=s.status_trend or "stable",
            created_at=s.created_at,
        )
        for s in snapshots
    ]
