"""
Risks Router — AI Software Engineering Intelligence Platform.

Endpoints for predictive risk analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.risk_predictor import predict_project_risks
from app.agents.config import default_config

router = APIRouter(prefix="/projects", tags=["Risks"])


@router.get("/{project_id}/risks", response_model=schemas.RiskPredictionReportResponse)
def get_project_risks(project_id: int, db: Session = Depends(get_db)):
    """
    Run predictive risk analysis from historical metric trends.
    Explicitly flags insufficient data when < 4 points exist.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        return schemas.RiskPredictionReportResponse(
            overall_risk_level="insufficient_data",
            risks=[],
            top_vulnerability="No metric telemetry recorded",
        )

    latest_metrics_map = {}
    history_map = {}
    for val_row, defn in metric_rows:
        latest_metrics_map[defn.key] = {
            "id": defn.id,
            "metric_id": defn.id,
            "display_name": defn.display_name,
            "category": defn.category,
            "unit": defn.unit,
            "higher_is_better": defn.higher_is_better,
            "value": float(val_row.value),
        }
        history = crud.get_metric_history(db, project_id, defn.id, limit=20)
        history_map[defn.id] = list(reversed(history))

    cfg = default_config()
    risk_report = predict_project_risks(latest_metrics_map, history_map, cfg)

    # Save predictions
    crud.save_risk_predictions(db, project_id, risk_report.risks)

    return schemas.RiskPredictionReportResponse(
        overall_risk_level=risk_report.overall_risk_level,
        risks=[
            schemas.RiskItemResponse(
                risk_category=r.risk_category,
                title=r.title,
                risk_level=r.risk_level,
                probability=r.probability,
                affected_metric=r.affected_metric,
                reason=r.reason,
                confidence=r.confidence,
                recommended_mitigation=r.recommended_mitigation,
                has_sufficient_data=r.has_sufficient_data,
                data_points_count=r.data_points_count,
            )
            for r in risk_report.risks
        ],
        top_vulnerability=risk_report.top_vulnerability,
        evaluated_at=risk_report.evaluated_at,
    )
