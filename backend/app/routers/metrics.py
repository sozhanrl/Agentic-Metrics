from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/definitions", response_model=list[schemas.MetricDefinitionResponse])
def list_metric_definitions(db: Session = Depends(get_db)):
    return crud.get_metric_definitions(db)


@router.post("/values", response_model=schemas.MetricValueResponse)
def record_metric_value(value: schemas.MetricValueCreate, db: Session = Depends(get_db)):
    return crud.create_metric_value(db, value)


@router.get("/latest/{project_id}", response_model=list[schemas.MetricValueWithDefinition])
def get_latest_metrics(project_id: int, db: Session = Depends(get_db)):
    rows = crud.get_latest_metric_values(db, project_id)
    result = []
    for value, definition in rows:
        result.append(schemas.MetricValueWithDefinition(
            id=value.id,
            metric_key=definition.key,
            display_name=definition.display_name,
            category=definition.category,
            unit=definition.unit,
            higher_is_better=definition.higher_is_better,
            value=float(value.value),
            recorded_at=value.recorded_at,
        ))
    return result


from sqlalchemy import desc
from app import models

@router.get("/history/{project_id}/{metric_id}", response_model=list[schemas.MetricValueResponse])
def get_metric_history(project_id: int, metric_id: int, limit: int = 30, db: Session = Depends(get_db)):
    return crud.get_metric_history(db, project_id, metric_id, limit)


@router.get("/history-all/{project_id}")
def get_all_metrics_history(project_id: int, limit: int = 15, db: Session = Depends(get_db)):
    """
    Returns history for all metrics of a project, grouped by metric_id, sorted oldest to newest.
    """
    values = (
        db.query(models.MetricValue)
        .filter(models.MetricValue.project_id == project_id)
        .order_by(models.MetricValue.metric_id, desc(models.MetricValue.recorded_at))
        .all()
    )

    grouped = {}
    for val in values:
        m_id = val.metric_id
        if m_id not in grouped:
            grouped[m_id] = []
        if len(grouped[m_id]) < limit:
            grouped[m_id].append({
                "id": val.id,
                "project_id": val.project_id,
                "metric_id": val.metric_id,
                "value": float(val.value),
                "recorded_at": val.recorded_at,
            })

    for m_id in grouped:
        grouped[m_id].reverse()

    return grouped

