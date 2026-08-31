from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app import crud, schemas
from app.agents.orchestrator import run_pipeline, EnrichedRecommendation
from app.agents.action_planner import build_action_plan
from app.agents.goal_optimizer import optimize_recommendations
from app.ai_engine import narrate_recommendation, is_enabled as ai_enabled

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

TRAIL_MARKER = "\n---REASONING_TRAIL---\n"
AGENT_TRAIL_MARKER = "\n---AGENT_TRAIL---\n"


def _pack(explanation: str, trail: list[str]) -> str:
    return explanation + TRAIL_MARKER + "\n".join(trail)


def _unpack(stored: str) -> tuple[str, list[str]]:
    if TRAIL_MARKER in stored:
        explanation, trail_block = stored.split(TRAIL_MARKER, 1)
        if AGENT_TRAIL_MARKER in trail_block:
            trail_block = trail_block.split(AGENT_TRAIL_MARKER, 1)[0]
        return explanation, [line for line in trail_block.split("\n") if line]
    return stored, []


from app.disclosure import serialize_recommendation_response


def _to_response(rec, agent_trail=None, adaptive_weights=None,
                 trend_slope=0.0, conflict_note=None,
                 detected_domain=None, confidence_score=0.0,
                 confidence_label="low", confidence_evidence=None,
                 metric_key="general") -> dict:
    explanation, trail = _unpack(rec.explanation)
    conf_val = confidence_score or 0.75
    conf_lbl = confidence_label or ("high" if conf_val >= 0.7 else ("medium" if conf_val >= 0.45 else "low"))

    # Generate structured action plan
    action_plan_obj = build_action_plan(
        metric_key=metric_key,
        title=rec.title,
        priority_score=float(rec.priority_score),
        confidence_score=float(conf_val),
    )

    action_plan_dict = {
        "problem": action_plan_obj.problem,
        "why_it_matters": action_plan_obj.why_it_matters,
        "root_cause": action_plan_obj.root_cause,
        "recommended_action": action_plan_obj.recommended_action,
        "expected_impact": action_plan_obj.expected_impact,
        "estimated_effort": action_plan_obj.estimated_effort,
        "priority": action_plan_obj.priority,
        "confidence_pct": action_plan_obj.confidence_pct,
        "success_criteria": action_plan_obj.success_criteria,
    }

    full_dict = {
        "id":                  rec.id,
        "project_id":          rec.project_id,
        "title":               rec.title,
        "explanation":         explanation,
        "reasoning_trail":     trail,
        "agent_trail":         agent_trail or [],
        "adaptive_weights":    adaptive_weights,
        "trend_slope":         trend_slope,
        "conflict_note":       conflict_note,
        "detected_domain":     detected_domain,
        "confidence_score":    conf_val,
        "confidence_label":    conf_lbl,
        "confidence_evidence": confidence_evidence or [],
        "priority_score":      float(rec.priority_score),
        "related_metrics":     rec.related_metrics,
        "status":              rec.status,
        "action_plan":         action_plan_dict,
        "created_at":          rec.created_at,
        "resolved_at":         rec.resolved_at,
        "ai_narrated":         ai_enabled(),
    }

    return serialize_recommendation_response(full_dict)



def generate_recommendations_for_project(db: Session, project_id: int) -> list[dict]:
    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        raise HTTPException(
            status_code=404,
            detail="No metric values found for this project. Record some metrics first.",
        )

    history_map: dict[int, list] = {}
    for _, definition in metric_rows:
        history = crud.get_metric_history(db, project_id, definition.id, limit=10)
        history_map[definition.id] = list(reversed(history))

    project = crud.get_project(db, project_id)
    risk_profile = crud.get_risk_profile(db, project_id)
    base_weights = crud.get_latest_weights(db, project_id)
    weight_sample_sizes = crud.get_weight_sample_sizes(db, project_id)
    graph_edges = crud.get_latest_dependency_edges(db, project_id)
    dependency_edges = {e.target_metric_key: e for e in graph_edges}
    metric_learning_weights = crud.get_metric_weights(db, project_id)
    causal_edges = crud.get_active_causal_edges(db, project_id)

    from app.agents.context_memory_engine import build_context_key
    ctx_key = build_context_key(project, risk_profile)
    context_memories = crud.get_context_memory_by_key(db, ctx_key)

    enriched: list[EnrichedRecommendation] = run_pipeline(
        metric_rows=metric_rows,
        history_map=history_map,
        risk_profile=risk_profile,
        base_weights=base_weights,
        graph_edges=graph_edges,
        project=project,
        weight_sample_sizes=weight_sample_sizes,
        dependency_edges=dependency_edges,
        metric_learning_weights=metric_learning_weights,
        causal_edges=causal_edges,
        context_memories=context_memories,
    )

    crud.clear_open_recommendations(db, project_id)

    metric_def_map = {d.id: d.key for _, d in metric_rows}

    created = []
    for rec in enriched:
        narrated_explanation = narrate_recommendation(
            rec.title, rec.explanation, rec.reasoning_trail
        )
        stored_explanation = _pack(narrated_explanation, rec.reasoning_trail)

        db_rec = crud.create_recommendation(
            db,
            project_id=project_id,
            title=rec.title,
            explanation=stored_explanation,
            priority_score=rec.priority_score,
            related_metrics=rec.related_metric_ids,
        )

        m_key = "general"
        if rec.related_metric_ids and rec.related_metric_ids[0] in metric_def_map:
            m_key = metric_def_map[rec.related_metric_ids[0]]

        created.append(
            _to_response(
                db_rec,
                agent_trail=rec.agent_trail,
                adaptive_weights=rec.adaptive_weights,
                trend_slope=rec.trend_slope,
                conflict_note=rec.conflict_note,
                detected_domain=rec.detected_domain,
                confidence_score=rec.confidence_score,
                confidence_label=rec.confidence_label,
                confidence_evidence=rec.confidence_evidence,
                metric_key=m_key,
            )
        )

    return created


@router.post("/{project_id}/generate")
def generate(project_id: int, db: Session = Depends(get_db)):
    return generate_recommendations_for_project(db, project_id)


@router.get("/{project_id}")
def list_recommendations(
    project_id: int,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    recs = crud.get_recommendations(db, project_id, status)
    metric_rows = crud.get_latest_metric_values(db, project_id)
    metric_def_map = {d.id: d.key for _, d in metric_rows}

    results = []
    for r in recs:
        m_key = "general"
        if r.related_metrics and r.related_metrics[0] in metric_def_map:
            m_key = metric_def_map[r.related_metrics[0]]
        results.append(_to_response(r, metric_key=m_key))

    return results


@router.patch("/{recommendation_id}/status")
def update_status(
    recommendation_id: int,
    update: schemas.RecommendationStatusUpdate,
    db: Session = Depends(get_db),
):
    rec = crud.update_recommendation_status(db, recommendation_id, update.status)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _to_response(rec)


# ---------------------------------------------------------------------------
# Recommendation Lifecycle Endpoints (Phase 1 & 5)
# ---------------------------------------------------------------------------

@router.post("/{recommendation_id}/start")
def start_recommendation(
    recommendation_id: int,
    payload: Optional[schemas.RecommendationActionCreate] = None,
    db: Session = Depends(get_db),
):
    """
    Transition recommendation to 'in_progress' and log start action.
    """
    rec = crud.get_recommendation(db, recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "in_progress"
    db.commit()
    db.refresh(rec)

    crud.log_recommendation_action(
        db=db,
        recommendation_id=recommendation_id,
        action_type="start",
        notes=payload.notes if payload else "Action plan execution initiated.",
    )

    crud.log_project_event(
        db=db,
        project_id=rec.project_id,
        event_type="ai_intervention",
        title=f"Action Started: {rec.title}",
        description=f"Engineer commenced remediation on recommendation #{rec.id}.",
    )

    return _to_response(rec)


@router.post("/{recommendation_id}/resolve")
def resolve_recommendation(
    recommendation_id: int,
    payload: Optional[schemas.RecommendationActionCreate] = None,
    db: Session = Depends(get_db),
):
    """
    Transition recommendation to 'actioned' / 'resolved' and record timestamp.
    """
    rec = crud.get_recommendation(db, recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "actioned"
    rec.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)

    crud.log_recommendation_action(
        db=db,
        recommendation_id=recommendation_id,
        action_type="resolve",
        notes=payload.notes if payload else "Remediation marked resolved. Awaiting verification.",
    )

    crud.log_project_event(
        db=db,
        project_id=rec.project_id,
        event_type="rec_resolved",
        title=f"Recommendation Resolved: {rec.title}",
        description=f"Action marked completed. Telemetry verification pending.",
    )

    return _to_response(rec)


@router.post("/{recommendation_id}/verify", response_model=schemas.RecommendationOutcomeResponse)
def verify_recommendation_outcome(
    recommendation_id: int,
    db: Session = Depends(get_db),
):
    """
    Compare the related metric before and after intervention.
    Calculates improvement percentage, checks goal achievement, and feeds back into self-learning.
    """
    rec = crud.get_recommendation(db, recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    metric_id = rec.related_metrics[0] if rec.related_metrics else None
    if not metric_id:
        raise HTTPException(status_code=400, detail="Recommendation has no associated metric to verify.")

    defn = crud.get_metric_definition(db, metric_id)
    if not defn:
        raise HTTPException(status_code=404, detail="Metric definition not found.")

    history = crud.get_metric_history(db, rec.project_id, metric_id, limit=10)
    if not history:
        raise HTTPException(status_code=400, detail="No historical telemetry available for verification.")

    after_val = float(history[0].value)
    before_val = float(history[-1].value) if len(history) > 1 else after_val

    if defn.higher_is_better:
        improvement = ((after_val - before_val) / max(1e-4, abs(before_val))) * 100.0
        achieved = after_val >= before_val
    else:
        improvement = ((before_val - after_val) / max(1e-4, abs(before_val))) * 100.0
        achieved = after_val <= before_val

    # Record outcome
    outcome = crud.record_recommendation_outcome(
        db=db,
        recommendation_id=recommendation_id,
        project_id=rec.project_id,
        metric_key=defn.key,
        before_value=before_val,
        after_value=after_val,
        improvement_pct=round(improvement, 2),
        goal_achieved=achieved,
    )

    # Feed outcome back to recommendation feedback
    crud.create_feedback(
        db=db,
        feedback=schemas.FeedbackCreate(
            recommendation_id=recommendation_id,
            was_helpful=achieved,
            user_comment=f"Automated verification: Metric improved by {improvement:+.1f}%. Goal achieved: {achieved}.",
            outcome_metric_id=metric_id,
            outcome_delta=improvement,
        )
    )

    return schemas.RecommendationOutcomeResponse(
        id=outcome.id,
        recommendation_id=outcome.recommendation_id,
        project_id=outcome.project_id,
        metric_key=outcome.metric_key,
        before_value=float(outcome.before_value),
        after_value=float(outcome.after_value),
        improvement_pct=float(outcome.improvement_pct),
        goal_achieved=outcome.goal_achieved,
        measured_at=outcome.measured_at,
    )


@router.get("/{recommendation_id}/outcome", response_model=schemas.RecommendationOutcomeResponse)
def get_recommendation_outcome_endpoint(recommendation_id: int, db: Session = Depends(get_db)):
    outcome = crud.get_recommendation_outcome(db, recommendation_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="No verification outcome recorded yet for this recommendation.")
    return schemas.RecommendationOutcomeResponse(
        id=outcome.id,
        recommendation_id=outcome.recommendation_id,
        project_id=outcome.project_id,
        metric_key=outcome.metric_key,
        before_value=float(outcome.before_value),
        after_value=float(outcome.after_value),
        improvement_pct=float(outcome.improvement_pct),
        goal_achieved=outcome.goal_achieved,
        measured_at=outcome.measured_at,
    )


# ---------------------------------------------------------------------------
# Goal Optimizer Endpoint (Wires goal_optimizer.py!)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/optimize")
def optimize_recommendations_endpoint(
    project_id: int,
    constraints: Optional[list[schemas.GoalConstraintCreate]] = None,
    db: Session = Depends(get_db),
):
    """
    Rerank recommendations according to user-supplied or active database goal constraints
    (risk budget, cost limit, sprint duration).
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch active recommendations
    recs = crud.get_recommendations(db, project_id, status="open")
    if not recs:
        return {"project_id": project_id, "optimized_recommendations": [], "message": "No open recommendations to optimize."}

    # Fetch constraints from DB or payload
    active_constraints = []
    if constraints:
        for c in constraints:
            class MockConstraint:
                def __init__(self, ctype, cval):
                    self.constraint_type = ctype
                    self.constraint_value = cval
            active_constraints.append(MockConstraint(c.constraint_type, c.constraint_value))
    else:
        active_constraints = crud.get_active_goal_constraints(db, project_id)

    bayesian_states = crud.get_metric_weights(db, project_id)

    # Format for optimizer
    scored_items = []
    for r in recs:
        class MockSignal:
            def __init__(self, key, sev, title):
                self.key = key
                self.severity = sev
                self.title = title
        sig = MockSignal("general", max(0.5, float(r.priority_score) / 50.0), r.title)
        scored_items.append((sig, float(r.priority_score), None))

    opt_results = optimize_recommendations(
        scored_recommendations=scored_items,
        active_constraints=active_constraints,
        bayesian_states=bayesian_states,
    )

    return {
        "project_id": project_id,
        "optimized_recommendations": [
            {
                "title": r.recommendation.title,
                "priority_score": r.priority_score,
                "adjusted_score": r.adjusted_score,
                "risk_impact": r.risk_impact,
                "cost_estimate": r.cost_estimate,
                "time_estimate": r.time_estimate,
                "constraint_status": r.constraint_status,
            }
            for r in opt_results
        ],
    }
