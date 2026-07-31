"""
Analytics Router — feedback analytics endpoints for the dashboard.

These endpoints power the Feedback Analytics tab in the React frontend.
They read from the enriched recommendation_feedback rows (populated by the CSV seed).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/feedback/summary", response_model=schemas.FeedbackAnalyticsSummary)
def get_feedback_analytics_summary(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    category: Optional[str] = Query(None, description="Filter by category: code_quality | process | devops"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    db: Session = Depends(get_db),
):
    """
    Full aggregated analytics summary — KPIs, breakdowns by category/role/metric/project,
    and daily helpfulness trends. Used to power the entire analytics dashboard.
    """
    data = crud.build_feedback_analytics_summary(
        db, project_id=project_id, category=category, user_role=user_role
    )
    return data


@router.get("/feedback/rows", response_model=list[schemas.FeedbackAnalyticsRow])
def get_feedback_analytics_rows(
    project_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    user_role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return raw enriched feedback rows (for table views / CSV export).
    """
    rows = crud.get_all_feedback_analytics(
        db, project_id=project_id, category=category, user_role=user_role
    )
    return rows


@router.get("/feedback/filters")
def get_feedback_filter_options(db: Session = Depends(get_db)):
    """
    Return distinct filter option values present in the data (projects, roles, categories).
    Used to populate filter dropdowns in the frontend.
    """
    from app import models
    from sqlalchemy import distinct

    roles = [
        r[0] for r in
        db.query(distinct(models.RecommendationFeedback.user_role))
        .filter(models.RecommendationFeedback.user_role.isnot(None))
        .order_by(models.RecommendationFeedback.user_role)
        .all()
    ]
    categories = [
        r[0] for r in
        db.query(distinct(models.RecommendationFeedback.category))
        .filter(models.RecommendationFeedback.category.isnot(None))
        .order_by(models.RecommendationFeedback.category)
        .all()
    ]
    project_ids = [
        r[0] for r in
        db.query(distinct(models.RecommendationFeedback.project_id))
        .filter(models.RecommendationFeedback.project_id.isnot(None))
        .order_by(models.RecommendationFeedback.project_id)
        .all()
    ]
    # Enrich project IDs with names
    projects = []
    for pid in project_ids:
        p = crud.get_project(db, pid)
        projects.append({"id": pid, "name": p.name if p else f"Project {pid}"})

    return {
        "roles": roles,
        "categories": categories,
        "projects": projects,
    }
