from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.recommendation_engine import generate_recommendations
from app.ai_engine import narrate_recommendation, is_enabled as ai_enabled

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

# Explanation and reasoning trail are stored together in one TEXT column,
# separated by this marker, so no schema change is needed to persist the
# trail. The frontend splits on this marker to render them separately.
TRAIL_MARKER = "\n---REASONING_TRAIL---\n"


def _pack(explanation: str, trail: list[str]) -> str:
    return explanation + TRAIL_MARKER + "\n".join(trail)


def _unpack(stored: str) -> tuple[str, list[str]]:
    if TRAIL_MARKER in stored:
        explanation, trail_block = stored.split(TRAIL_MARKER, 1)
        return explanation, [line for line in trail_block.split("\n") if line]
    return stored, []


def _to_response_with_trail(rec):
    explanation, trail = _unpack(rec.explanation)
    return {
        "id": rec.id,
        "project_id": rec.project_id,
        "title": rec.title,
        "explanation": explanation,
        "reasoning_trail": trail,
        "priority_score": float(rec.priority_score),
        "related_metrics": rec.related_metrics,
        "status": rec.status,
        "created_at": rec.created_at,
        "resolved_at": rec.resolved_at,
        "ai_narrated": ai_enabled(),
    }


@router.post("/{project_id}/generate")
def generate(project_id: int, db: Session = Depends(get_db)):
    """
    Runs the agent pipeline: pulls latest metrics for the project,
    evaluates and scores them, clears stale open recommendations, and
    persists the new ranked list.
    """
    metric_rows = crud.get_latest_metric_values(db, project_id)
    if not metric_rows:
        raise HTTPException(
            status_code=404,
            detail="No metric values found for this project. Record some metrics first.",
        )

    scored = generate_recommendations(metric_rows)
    crud.clear_open_recommendations(db, project_id)

    created = []
    for rec in scored:
        explanation = narrate_recommendation(rec.title, rec.explanation, rec.reasoning_trail)
        stored_explanation = _pack(explanation, rec.reasoning_trail)
        db_rec = crud.create_recommendation(
            db, project_id=project_id, title=rec.title,
            explanation=stored_explanation, priority_score=rec.priority_score,
            related_metrics=rec.related_metric_ids,
        )
        created.append(_to_response_with_trail(db_rec))

    return created


@router.get("/{project_id}")
def list_recommendations(project_id: int, status: str | None = None, db: Session = Depends(get_db)):
    recs = crud.get_recommendations(db, project_id, status)
    return [_to_response_with_trail(r) for r in recs]


@router.patch("/{recommendation_id}/status")
def update_status(recommendation_id: int, update: schemas.RecommendationStatusUpdate, db: Session = Depends(get_db)):
    rec = crud.update_recommendation_status(db, recommendation_id, update.status)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _to_response_with_trail(rec)
