"""
Timeline Router — AI Software Engineering Intelligence Platform.

Endpoints for project event timeline (metric degradation, improvements, recommendations, interventions).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/projects", tags=["Timeline"])


@router.get("/{project_id}/timeline", response_model=list[schemas.ProjectEventResponse])
def get_timeline(
    project_id: int,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get aggregated project event timeline.
    If no events are logged yet, automatically synthesizes events from recommendation history,
    metric records, weight updates, and anomaly snapshots.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    events = crud.get_project_events(db, project_id, event_type=event_type, limit=limit)

    if not events:
        # Synthesize baseline events from existing database data
        recs = crud.get_recommendations(db, project_id)
        for r in recs[:5]:
            crud.log_project_event(
                db=db,
                project_id=project_id,
                event_type="rec_generated",
                title=f"Recommendation Generated: {r.title}",
                description=f"Priority Score: {r.priority_score}. Status: {r.status}",
                metadata_json={"recommendation_id": r.id, "priority_score": float(r.priority_score)},
            )
        weight_hist = crud.get_weight_history(db, project_id, limit=5)
        for w in weight_hist:
            crud.log_project_event(
                db=db,
                project_id=project_id,
                event_type="ai_intervention",
                title=f"Adaptive Weight Adjusted: {w.category}",
                description=f"Weight shifted from {w.old_weight:.2f} to {w.new_weight:.2f} via {w.source}.",
                metadata_json={"category": w.category, "source": w.source},
            )
        events = crud.get_project_events(db, project_id, event_type=event_type, limit=limit)

    return events
