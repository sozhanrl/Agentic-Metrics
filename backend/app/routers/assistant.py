"""
Assistant Router — AI Software Engineering Intelligence Platform.

Endpoints for interacting with the AI Software Engineering Assistant.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.ai_assistant import ask_assistant
from app.agents.health_scorer import compute_health_score
from app.agents.anomaly_detector import detect_metric_anomalies
from app.agents.risk_predictor import predict_project_risks
from app.agents.perceiver import perceive_all
from app.agents.config import default_config

router = APIRouter(prefix="/projects", tags=["AI Assistant"])


@router.post("/{project_id}/ask", response_model=schemas.AssistantResponseSchema)
def ask_project_assistant(project_id: int, payload: schemas.AssistantQuestionRequest, db: Session = Depends(get_db)):
    """
    Ask a question to the AI Software Engineering Assistant.
    Grounds all answers strictly in actual project metrics, recommendations,
    health snapshots, causal graph, and risk indicators.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    history_map = {}
    for _, defn in metric_rows:
        history = crud.get_metric_history(db, project_id, defn.id, limit=15)
        history_map[defn.id] = list(reversed(history))

    cfg = default_config()
    signals = perceive_all(metric_rows, history_map, cfg)
    base_weights = crud.get_latest_weights(db, project_id)
    recommendations = crud.get_recommendations(db, project_id)
    latest_snapshot = crud.get_latest_health_snapshot(db, project_id)

    health_breakdown = compute_health_score(
        signals=signals,
        recommendations=recommendations,
        previous_snapshot=latest_snapshot,
        adaptive_weights=base_weights,
        cfg=cfg,
    )

    anomalies = detect_metric_anomalies(metric_rows, history_map, cfg)

    latest_metrics_map = {
        defn.key: {
            "id": defn.id,
            "metric_key": defn.key,
            "display_name": defn.display_name,
            "category": defn.category,
            "unit": defn.unit,
            "value": float(val_row.value),
        }
        for val_row, defn in metric_rows
    }
    risk_report = predict_project_risks(latest_metrics_map, history_map, cfg)
    causal_edges = crud.get_active_causal_edges(db, project_id)

    # Format data for assistant
    health_dict = {
        "overall_score": health_breakdown.overall_score,
        "code_quality_score": health_breakdown.code_quality_score,
        "process_score": health_breakdown.process_score,
        "devops_score": health_breakdown.devops_score,
        "ai_risk_score": health_breakdown.ai_risk_score,
        "status_trend": health_breakdown.status_trend,
    }

    metrics_list = [
        {
            "metric_key": defn.key,
            "display_name": defn.display_name,
            "value": float(val_row.value),
            "unit": defn.unit or "",
            "category": defn.category,
            "deviation_pct": next((s.deviation_pct for s in signals if s.key == defn.key), 0.0),
        }
        for val_row, defn in metric_rows
    ]

    recs_list = [
        {
            "id": r.id,
            "title": r.title,
            "priority_score": float(r.priority_score),
            "explanation": r.explanation,
            "status": r.status,
        }
        for r in recommendations
    ]

    anoms_list = [
        {
            "metric_name": a.metric_name,
            "current_value": a.current_value,
            "unit": a.unit,
            "z_score": a.z_score,
            "severity": a.severity,
            "possible_cause": a.possible_cause,
            "recommended_action": a.recommended_action,
        }
        for a in anomalies
    ]

    risks_list = [
        {
            "title": r.title,
            "risk_level": r.risk_level,
            "probability": r.probability,
            "reason": r.reason,
            "mitigation": r.recommended_mitigation,
        }
        for r in risk_report.risks
    ]

    response = ask_assistant(
        question=payload.question,
        project_name=project.name,
        health_data=health_dict,
        latest_metrics=metrics_list,
        recommendations=recs_list,
        anomalies=anoms_list,
        risks=risks_list,
        causal_edges=causal_edges,
    )

    return schemas.AssistantResponseSchema(
        question=response.question,
        answer=response.answer,
        evidence_points=response.evidence_points,
        suggested_followups=response.suggested_followups,
        source_artifacts=response.source_artifacts,
        responded_at=response.responded_at,
    )
