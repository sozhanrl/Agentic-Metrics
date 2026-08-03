"""
Recommendations Router

The `generate` endpoint is the main entry point for the multi-agent pipeline.
It now calls the Orchestrator (which chains Perceiver → AdaptiveWeighter →
Evaluator → Negotiator → Explainer) instead of the old monolithic
recommendation_engine.py. The old engine is preserved for reference but is
no longer invoked.

Backward compatibility
----------------------
The GET list endpoint continues to unpack the TRAIL_MARKER format so that
existing recommendations persisted by the old engine are still readable.
New recommendations from the multi-agent engine pack the trail the same way,
so no migration is needed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.orchestrator import run_pipeline, EnrichedRecommendation
from app.ai_engine import narrate_recommendation, is_enabled as ai_enabled

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

# Explanation and reasoning trail stored in the same TEXT column, separated
# by this marker. Frontend splits on it; old and new engines both use it.
TRAIL_MARKER = "\n---REASONING_TRAIL---\n"

# Separator between structured agent_trail JSON and the legacy reasoning trail
# inside the same explanation field, for backward-compat storage.
AGENT_TRAIL_MARKER = "\n---AGENT_TRAIL---\n"


def _pack(explanation: str, trail: list[str]) -> str:
    return explanation + TRAIL_MARKER + "\n".join(trail)


def _unpack(stored: str) -> tuple[str, list[str]]:
    if TRAIL_MARKER in stored:
        explanation, trail_block = stored.split(TRAIL_MARKER, 1)
        # Strip any agent_trail section that may have been appended
        if AGENT_TRAIL_MARKER in trail_block:
            trail_block = trail_block.split(AGENT_TRAIL_MARKER, 1)[0]
        return explanation, [line for line in trail_block.split("\n") if line]
    return stored, []


def _to_response(rec, agent_trail=None, adaptive_weights=None,
                 trend_slope=0.0, conflict_note=None,
                 detected_domain=None, confidence_score=0.0,
                 confidence_label="low", confidence_evidence=None) -> dict:
    """
    Build the enriched recommendation dict for API responses.
    Works for both freshly-generated recs (where we pass extra context) and
    for DB-loaded recs (where we only have the packed explanation string).
    """
    explanation, trail = _unpack(rec.explanation)
    return {
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
        "confidence_score":    confidence_score,
        "confidence_label":    confidence_label,
        "confidence_evidence": confidence_evidence or [],
        "priority_score":      float(rec.priority_score),
        "related_metrics":     rec.related_metrics,
        "status":              rec.status,
        "created_at":          rec.created_at,
        "resolved_at":         rec.resolved_at,
        "ai_narrated":         ai_enabled(),
    }


# ---------------------------------------------------------------------------
# Generate endpoint — runs the multi-agent pipeline
# ---------------------------------------------------------------------------

@router.post("/{project_id}/generate")
def generate(project_id: int, db: Session = Depends(get_db)):
    """
    Run the full multi-agent pipeline for a project:
      Perceiver → AdaptiveWeighter → ContextDetector → Evaluator → Negotiator → Explainer → ConfidenceEstimator

    Clears stale 'open' recommendations, then persists and returns the new
    enriched ranked list, including agent provenance trails and adaptive weights.
    """
    # --- Fetch input data ---------------------------------------------------
    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        raise HTTPException(
            status_code=404,
            detail="No metric values found for this project. Record some metrics first.",
        )

    # Build history map for trend detection: { metric_id → [MetricValue…] oldest-first }
    history_map: dict[int, list] = {}
    for _, definition in metric_rows:
        history = crud.get_metric_history(db, project_id, definition.id, limit=10)
        history_map[definition.id] = list(reversed(history))  # oldest → newest

    # Fetch Project row
    project = crud.get_project(db, project_id)

    # Load risk profile (None is safe — AdaptiveWeighter uses neutral defaults)
    risk_profile = crud.get_risk_profile(db, project_id)

    # Load the latest persisted weights for this project (or base defaults)
    base_weights = crud.get_latest_weights(db, project_id)

    # Pre-fetch feedback sample counts per category for ConfidenceEstimator
    weight_sample_sizes = crud.get_weight_sample_sizes(db, project_id)

    # Pre-fetch empirically discovered dependency edges for Negotiator and ConfidenceEstimator
    graph_edges = crud.get_latest_dependency_edges(db, project_id)
    dependency_edges = {e.target_metric_key: e for e in graph_edges}

    # --- Run the pipeline ---------------------------------------------------
    enriched: list[EnrichedRecommendation] = run_pipeline(
        metric_rows=metric_rows,
        history_map=history_map,
        risk_profile=risk_profile,
        base_weights=base_weights,
        graph_edges=graph_edges,
        project=project,
        weight_sample_sizes=weight_sample_sizes,
        dependency_edges=dependency_edges,
    )

    # --- Persist results ----------------------------------------------------
    crud.clear_open_recommendations(db, project_id)

    created = []
    for rec in enriched:
        # Optional LLM narration (ai_engine.py) rewrites the prose explanation.
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
            )
        )

    return created


# ---------------------------------------------------------------------------
# List / read endpoints — backward compatible
# ---------------------------------------------------------------------------

@router.get("/{project_id}")
def list_recommendations(
    project_id: int,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """
    List recommendations for a project, optionally filtered by status.
    Returns the same enriched shape as the generate endpoint (agent_trail will
    be empty for recommendations generated by the legacy engine).
    """
    recs = crud.get_recommendations(db, project_id, status)
    return [_to_response(r) for r in recs]


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
