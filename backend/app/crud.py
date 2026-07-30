from sqlalchemy.orm import Session
from sqlalchemy import desc
from app import models, schemas


# ---------- Projects ----------

def create_project(db: Session, project: schemas.ProjectCreate):
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_projects(db: Session):
    return db.query(models.Project).order_by(models.Project.name).all()


def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()


# ---------- Metric Definitions ----------

def get_metric_definitions(db: Session):
    return db.query(models.MetricDefinition).all()


def get_metric_definition(db: Session, metric_id: int):
    return db.query(models.MetricDefinition).filter(models.MetricDefinition.id == metric_id).first()


def get_metric_definition_by_key(db: Session, key: str):
    return db.query(models.MetricDefinition).filter(models.MetricDefinition.key == key).first()


# ---------- Metric Values ----------

def create_metric_value(db: Session, metric_value: schemas.MetricValueCreate):
    db_value = models.MetricValue(**metric_value.model_dump())
    db.add(db_value)
    db.commit()
    db.refresh(db_value)
    return db_value


def get_latest_metric_values(db: Session, project_id: int):
    """
    Returns the most recent value per metric for a project, joined with
    its definition, so the dashboard can render name/category/unit directly.
    """
    subq = (
        db.query(
            models.MetricValue.metric_id,
            desc(models.MetricValue.recorded_at)
        )
        .filter(models.MetricValue.project_id == project_id)
        .subquery()
    )

    rows = (
        db.query(models.MetricValue, models.MetricDefinition)
        .join(models.MetricDefinition, models.MetricValue.metric_id == models.MetricDefinition.id)
        .filter(models.MetricValue.project_id == project_id)
        .order_by(models.MetricValue.metric_id, desc(models.MetricValue.recorded_at))
        .all()
    )

    latest_by_metric = {}
    for value, definition in rows:
        if definition.id not in latest_by_metric:
            latest_by_metric[definition.id] = (value, definition)

    return list(latest_by_metric.values())


def get_metric_history(db: Session, project_id: int, metric_id: int, limit: int = 30):
    return (
        db.query(models.MetricValue)
        .filter(
            models.MetricValue.project_id == project_id,
            models.MetricValue.metric_id == metric_id,
        )
        .order_by(desc(models.MetricValue.recorded_at))
        .limit(limit)
        .all()
    )


# ---------- Recommendations ----------

def create_recommendation(db: Session, project_id: int, title: str, explanation: str,
                           priority_score: float, related_metrics: list[int]):
    rec = models.Recommendation(
        project_id=project_id,
        title=title,
        explanation=explanation,
        priority_score=priority_score,
        related_metrics=related_metrics,
        status="open",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def get_recommendations(db: Session, project_id: int, status: str | None = None):
    q = db.query(models.Recommendation).filter(models.Recommendation.project_id == project_id)
    if status:
        q = q.filter(models.Recommendation.status == status)
    return q.order_by(desc(models.Recommendation.priority_score)).all()


def get_recommendation(db: Session, recommendation_id: int):
    return db.query(models.Recommendation).filter(models.Recommendation.id == recommendation_id).first()


def update_recommendation_status(db: Session, recommendation_id: int, status: str):
    rec = get_recommendation(db, recommendation_id)
    if rec:
        rec.status = status
        db.commit()
        db.refresh(rec)
    return rec


def clear_open_recommendations(db: Session, project_id: int):
    """Used before regenerating recommendations, so we don't pile up stale ones."""
    db.query(models.Recommendation).filter(
        models.Recommendation.project_id == project_id,
        models.Recommendation.status == "open",
    ).delete()
    db.commit()


# ---------- Feedback ----------

def create_feedback(db: Session, feedback: schemas.FeedbackCreate):
    db_feedback = models.RecommendationFeedback(**feedback.model_dump())
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


def get_feedback_for_recommendation(db: Session, recommendation_id: int):
    return (
        db.query(models.RecommendationFeedback)
        .filter(models.RecommendationFeedback.recommendation_id == recommendation_id)
        .all()
    )
