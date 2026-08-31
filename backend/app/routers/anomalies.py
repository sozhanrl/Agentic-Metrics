"""
Anomalies Router — AI Software Engineering Intelligence Platform.

Endpoints for statistical anomaly detection and lifecycle management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.anomaly_detector import detect_metric_anomalies
from app.agents.config import default_config

router = APIRouter(prefix="/projects", tags=["Anomalies"])


@router.get("/{project_id}/anomalies", response_model=list[schemas.AnomalyResponse])
def get_project_anomalies(project_id: int, db: Session = Depends(get_db)):
    """
    Run statistical anomaly detection over project metrics and return detected anomalies.
    Persists newly discovered anomalies into the audit table.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        return []

    history_map = {}
    for _, definition in metric_rows:
        history = crud.get_metric_history(db, project_id, definition.id, limit=20)
        history_map[definition.id] = list(reversed(history))

    cfg = default_config()
    detected = detect_metric_anomalies(metric_rows, history_map, cfg)

    # Persist and return
    results = []
    for a in detected:
        db_anomaly = crud.create_anomaly(
            db=db,
            project_id=project_id,
            metric_key=a.metric_key,
            metric_name=a.metric_name,
            current_value=a.current_value,
            expected_min=a.expected_min,
            expected_max=a.expected_max,
            deviation_pct=a.deviation_pct,
            severity=a.severity,
            possible_cause=a.possible_cause,
            recommended_action=a.recommended_action,
        )
        results.append(schemas.AnomalyResponse(
            id=db_anomaly.id,
            project_id=project_id,
            metric_key=a.metric_key,
            metric_name=a.metric_name,
            current_value=a.current_value,
            expected_min=a.expected_min,
            expected_max=a.expected_max,
            deviation_pct=a.deviation_pct,
            severity=a.severity,
            possible_cause=a.possible_cause,
            recommended_action=a.recommended_action,
            is_acknowledged=False,
            detected_at=db_anomaly.detected_at,
        ))

    return results


@router.post("/anomalies/{anomaly_id}/acknowledge", response_model=schemas.AnomalyResponse)
def acknowledge_anomaly_endpoint(anomaly_id: int, db: Session = Depends(get_db)):
    """
    Mark an anomaly as acknowledged by the user.
    """
    anomaly = crud.acknowledge_anomaly(db, anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    return schemas.AnomalyResponse(
        id=anomaly.id,
        project_id=anomaly.project_id,
        metric_key=anomaly.metric_key,
        metric_name=anomaly.metric_name,
        current_value=float(anomaly.current_value),
        expected_min=float(anomaly.expected_min),
        expected_max=float(anomaly.expected_max),
        deviation_pct=float(anomaly.deviation_pct),
        severity=anomaly.severity,
        possible_cause=anomaly.possible_cause,
        recommended_action=anomaly.recommended_action,
        is_acknowledged=anomaly.is_acknowledged,
        detected_at=anomaly.detected_at,
    )
