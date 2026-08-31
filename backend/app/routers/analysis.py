"""
Analysis Router — AI Software Engineering Intelligence Platform.

Endpoints for Root Cause Analysis and What-If Simulation.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.root_cause_analyzer import analyze_root_cause
from app.agents.what_if_simulator import run_what_if_simulation
from app.agents.config import default_config

router = APIRouter(prefix="/projects", tags=["Analysis & Simulation"])


@router.get("/{project_id}/root-cause/{metric_key}", response_model=schemas.RootCauseResponse)
def get_root_cause_analysis(project_id: int, metric_key: str, db: Session = Depends(get_db)):
    """
    Perform deep causal backward-traversal from metric_key to uncover root cause factors.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    latest_metrics_map = {}
    for val_row, defn in metric_rows:
        latest_metrics_map[defn.key] = {
            "metric_id": defn.id,
            "display_name": defn.display_name,
            "category": defn.category,
            "unit": defn.unit,
            "higher_is_better": defn.higher_is_better,
            "value": float(val_row.value),
        }

    if metric_key not in latest_metrics_map:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_key}' has no recorded values in this project.")

    causal_edges = crud.get_active_causal_edges(db, project_id)
    dependency_edges = crud.get_latest_dependency_edges(db, project_id)
    cfg = default_config()

    rc_report = analyze_root_cause(
        target_metric_key=metric_key,
        latest_metrics_map=latest_metrics_map,
        causal_edges=causal_edges,
        dependency_edges=dependency_edges,
        cfg=cfg,
    )

    return schemas.RootCauseResponse(
        target_metric=rc_report.target_metric,
        target_display_name=rc_report.target_display_name,
        severity=rc_report.severity,
        summary=rc_report.summary,
        causal_chain=[
            schemas.CausalNodeResponse(
                metric_key=n.metric_key,
                display_name=n.display_name,
                category=n.category,
                current_value=n.current_value,
                unit=n.unit,
                deviation_pct=n.deviation_pct,
                is_root_cause=n.is_root_cause,
                relation_to_parent=n.relation_to_parent,
                edge_strength=n.edge_strength,
                confidence=n.confidence,
                evidence_type=n.evidence_type,
            )
            for n in rc_report.causal_chain
        ],
        contributing_metrics=rc_report.contributing_metrics,
        root_metric_key=rc_report.root_metric_key,
        root_metric_name=rc_report.root_metric_name,
        confidence_score=rc_report.confidence_score,
        evidence_summary=rc_report.evidence_summary,
        system_impact=rc_report.system_impact,
        recommended_intervention=rc_report.recommended_intervention,
    )


@router.post("/{project_id}/what-if", response_model=schemas.WhatIfResponse)
def simulate_what_if(project_id: int, payload: schemas.WhatIfRequest, db: Session = Depends(get_db)):
    """
    Run an in-memory What-If scenario sandbox.
    Calculates predicted health score, risk changes, and re-ranked recommendation priorities.
    STRICT: Never writes or alters database records.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        raise HTTPException(status_code=400, detail="Project has no metric values to simulate on.")

    risk_profile = crud.get_risk_profile(db, project_id)
    base_weights = crud.get_latest_weights(db, project_id)
    cfg = default_config()

    sim_res = run_what_if_simulation(
        metric_rows=metric_rows,
        simulated_values=payload.simulated_values,
        risk_profile=risk_profile,
        base_weights=base_weights,
        cfg=cfg,
    )

    return schemas.WhatIfResponse(
        baseline_health=sim_res.baseline_health,
        predicted_health=sim_res.predicted_health,
        health_delta=sim_res.health_delta,
        health_percentage_gain=sim_res.health_percentage_gain,
        baseline_risk=sim_res.baseline_risk,
        predicted_risk=sim_res.predicted_risk,
        risk_delta=sim_res.risk_delta,
        affected_metrics=sim_res.affected_metrics,
        recommendation_diffs=[
            schemas.SimulatedRecommendationDiffResponse(
                metric_key=d.metric_key,
                title=d.title,
                baseline_priority=d.baseline_priority,
                simulated_priority=d.simulated_priority,
                priority_delta=d.priority_delta,
                rank_before=d.rank_before,
                rank_after=d.rank_after,
                status=d.status,
            )
            for d in sim_res.recommendation_diffs
        ],
        projected_category_health=sim_res.projected_category_health,
        simulation_notes=sim_res.simulation_notes,
        is_simulation=True,
        simulated_at=sim_res.simulated_at,
    )
