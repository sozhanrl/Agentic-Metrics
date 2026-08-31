"""
Alerts Router — AI Software Engineering Intelligence Platform.

Endpoints for managing project alerts and notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/projects", tags=["Alerts"])


@router.get("/{project_id}/alerts", response_model=list[schemas.AlertResponse])
def get_project_alerts(
    project_id: int,
    unread_only: bool = Query(False, description="Filter only unread alerts"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get alerts for a project. Auto-generates alerts for critical metrics and anomalies if empty.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    alerts = crud.get_alerts(db, project_id, unread_only=unread_only, limit=limit)

    if not alerts:
        # Check recommendations for critical items
        recs = crud.get_recommendations(db, project_id)
        for r in recs:
            if float(r.priority_score) >= 60.0:
                crud.create_alert(
                    db=db,
                    project_id=project_id,
                    alert_type="critical",
                    title=f"Critical Priority: {r.title}",
                    message=f"Priority Score {r.priority_score} detected. Immediate attention recommended.",
                )
        alerts = crud.get_alerts(db, project_id, unread_only=unread_only, limit=limit)

    return alerts


@router.post("/alerts/{alert_id}/read", response_model=schemas.AlertResponse)
def mark_alert_as_read(alert_id: int, db: Session = Depends(get_db)):
    """
    Mark an alert as read.
    """
    alert = crud.mark_alert_read(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
