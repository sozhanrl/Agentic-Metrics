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


# ---------- Risk Profile ----------

def upsert_risk_profile(db: Session, project_id: int, data: schemas.RiskProfileCreate):
    """Insert or update the risk profile for a project."""
    existing = db.query(models.ProjectRiskProfile).filter(
        models.ProjectRiskProfile.project_id == project_id
    ).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        profile = models.ProjectRiskProfile(project_id=project_id, **data.model_dump())
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile


def get_risk_profile(db: Session, project_id: int):
    return (
        db.query(models.ProjectRiskProfile)
        .filter(models.ProjectRiskProfile.project_id == project_id)
        .first()
    )


# ---------- Category Weight History ----------

def log_weight_event(
    db: Session,
    project_id: int,
    category: str,
    old_weight: float,
    new_weight: float,
    source: str = "manual",
    reason: str | None = None,
):
    """Append a row to the weight audit ledger."""
    event = models.CategoryWeightHistory(
        project_id=project_id,
        category=category,
        old_weight=old_weight,
        new_weight=new_weight,
        source=source,
        reason=reason,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_weight_history(db: Session, project_id: int, limit: int = 100):
    """Return weight change events newest-first."""
    return (
        db.query(models.CategoryWeightHistory)
        .filter(models.CategoryWeightHistory.project_id == project_id)
        .order_by(desc(models.CategoryWeightHistory.created_at))
        .limit(limit)
        .all()
    )


def get_latest_weights(db: Session, project_id: int) -> dict[str, float]:
    """
    Returns the most-recent weight for each category, falling back to base defaults
    from config if no history exists yet for a project.
    """
    from app.agents.config import BASE_CATEGORY_WEIGHTS  # lazy import avoids circular dep

    rows = (
        db.query(models.CategoryWeightHistory)
        .filter(models.CategoryWeightHistory.project_id == project_id)
        .order_by(desc(models.CategoryWeightHistory.created_at))
        .all()
    )
    weights = dict(BASE_CATEGORY_WEIGHTS)  # start with defaults
    seen: set[str] = set()
    for row in rows:
        if row.category not in seen:
            weights[row.category] = float(row.new_weight)
            seen.add(row.category)
    return weights



# ---------- Feedback Aggregation (for Self-Learning) ----------

def _decay_weight(feedback_row, as_of, decay_factor: float) -> float:
    """
    Compute the exponential decay weight for one feedback row.

    weight = decay_factor ^ days_ago

    Uses feedback_at preferentially (when the opinion was given), falls back
    to created_at (when the row was ingested).  Both are None-safe.
    """
    import math

    ts = getattr(feedback_row, "feedback_at", None) or getattr(feedback_row, "created_at", None)
    if ts is None or as_of is None:
        return 1.0  # no timestamp → treat as maximally recent

    from datetime import timezone
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    days_ago = max(0.0, (as_of - ts).total_seconds() / 86400.0)
    return decay_factor ** days_ago


def get_project_decay_factor(db: Session, project_id: int) -> float:
    """
    Return the per-project feedback decay factor.

    Projects may override the global default via a stored value on their
    risk profile (stored in the 'notes' field as a JSON-encoded override,
    or as a future dedicated column).  For now, falls back to the global
    DEFAULT_DECAY_FACTOR from config.
    """
    from app.agents.config import DEFAULT_DECAY_FACTOR
    # Future: query a project_settings table or risk_profile.decay_factor column.
    # Currently returns the global default; override logic can be added here.
    return DEFAULT_DECAY_FACTOR


def get_feedback_summary(
    db: Session,
    project_id: int,
    as_of=None,
) -> dict:
    """
    Aggregate feedback for a project grouped by metric category, with optional
    exponential recency decay.

    Parameters
    ----------
    as_of : datetime | None
        If provided, feedback ages are measured relative to this timestamp
        and weighted by decay_factor^days_ago.  If None, current UTC time is used.

    Returns a dict:
      { category: { "total_w": float,         # decay-weighted total
                    "helpful_w": float,        # decay-weighted helpful count
                    "outcome_delta_sum_w": float } }
    """
    from datetime import datetime, timezone

    as_of = as_of or datetime.now(timezone.utc)
    decay_factor = get_project_decay_factor(db, project_id)

    recs = db.query(models.Recommendation).filter(
        models.Recommendation.project_id == project_id
    ).all()

    rec_ids = [r.id for r in recs]
    rec_metrics_map = {r.id: (r.related_metrics or []) for r in recs}

    if not rec_ids:
        return {}

    feedbacks = (
        db.query(models.RecommendationFeedback)
        .filter(models.RecommendationFeedback.recommendation_id.in_(rec_ids))
        .all()
    )

    summary: dict[str, dict] = {}

    for fb in feedbacks:
        w = _decay_weight(fb, as_of, decay_factor)
        metric_ids = rec_metrics_map.get(fb.recommendation_id, [])
        categories: set[str] = set()
        for mid in metric_ids:
            defn = get_metric_definition(db, mid)
            if defn:
                categories.add(defn.category)

        for cat in categories:
            if cat not in summary:
                summary[cat] = {"total_w": 0.0, "helpful_w": 0.0, "outcome_delta_sum_w": 0.0}
            summary[cat]["total_w"] += w
            if fb.was_helpful:
                summary[cat]["helpful_w"] += w
            if fb.outcome_delta is not None:
                summary[cat]["outcome_delta_sum_w"] += float(fb.outcome_delta) * w

    return summary


def get_feedback_summary_by_metric(
    db: Session,
    project_id: int,
    as_of=None,
) -> dict:
    """
    Aggregate feedback for a project grouped by metric_name, with exponential
    recency decay.  Uses the extended analytics columns on RecommendationFeedback
    (metric_name, category) which are populated by the CSV seed and rich
    feedback API.

    Returns a dict:
      { metric_name: { "total_w": float, "helpful_w": float,
                       "outcome_delta_sum_w": float, "category": str } }
    """
    from datetime import datetime, timezone

    as_of = as_of or datetime.now(timezone.utc)
    decay_factor = get_project_decay_factor(db, project_id)

    # Pull feedback rows that have metric_name populated (rich feedback rows).
    rows = (
        db.query(models.RecommendationFeedback)
        .filter(
            models.RecommendationFeedback.project_id == project_id,
            models.RecommendationFeedback.metric_name.isnot(None),
        )
        .all()
    )

    summary: dict[str, dict] = {}

    for fb in rows:
        metric_name = fb.metric_name
        if not metric_name:
            continue

        w = _decay_weight(fb, as_of, decay_factor)
        if metric_name not in summary:
            summary[metric_name] = {
                "total_w": 0.0,
                "helpful_w": 0.0,
                "outcome_delta_sum_w": 0.0,
                "category": fb.category or "unknown",
            }

        summary[metric_name]["total_w"] += w
        if fb.was_helpful:
            summary[metric_name]["helpful_w"] += w
        if fb.outcome_delta is not None:
            summary[metric_name]["outcome_delta_sum_w"] += float(fb.outcome_delta) * w

    return summary


# ---------- Metric Weights (per-metric self-learning state) ----------

def upsert_metric_weight(
    db: Session,
    project_id: int,
    metric_name: str,
    weight: float,
    confidence: float,
    sample_count: float,
    trend: str,
) -> "models.MetricWeight":
    """
    Insert or update the per-metric learning state for one (project, metric) pair.
    The metric_weights table has a UNIQUE(project_id, metric_name) constraint so
    this is a true upsert: create if absent, overwrite if present.
    """
    from datetime import datetime, timezone

    existing = (
        db.query(models.MetricWeight)
        .filter(
            models.MetricWeight.project_id == project_id,
            models.MetricWeight.metric_name == metric_name,
        )
        .first()
    )

    if existing:
        existing.weight       = round(weight, 4)
        existing.confidence   = round(min(1.0, max(0.0, confidence)), 4)
        existing.sample_count = round(sample_count, 4)
        existing.trend        = trend
        existing.last_updated = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    row = models.MetricWeight(
        project_id   = project_id,
        metric_name  = metric_name,
        weight       = round(weight, 4),
        confidence   = round(min(1.0, max(0.0, confidence)), 4),
        sample_count = round(sample_count, 4),
        trend        = trend,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_metric_weights(db: Session, project_id: int) -> dict[str, dict]:
    """
    Return current per-metric learning state as a dict keyed by metric_name.

    { metric_name: { "weight": float, "confidence": float,
                     "sample_count": float, "trend": str } }
    """
    rows = (
        db.query(models.MetricWeight)
        .filter(models.MetricWeight.project_id == project_id)
        .all()
    )
    return {
        r.metric_name: {
            "weight":       float(r.weight),
            "confidence":   float(r.confidence),
            "sample_count": float(r.sample_count),
            "trend":        r.trend,
        }
        for r in rows
    }


# ---------- Learning Validation (P3 — Prove learning works) ----------

def get_learning_validation_report(db: Session, project_id: int) -> dict:
    """
    Compare recommendation quality before and after each self-learning weight
    update cycle for this project.

    For each category that has at least one weight-update event:
      - "pre_update" cohort  : feedback on recommendations created BEFORE that
                               weight update (i.e. under the OLD weights)
      - "post_update" cohort : feedback on recommendations created AFTER that
                               weight update (i.e. under the NEW weights)

    Metrics computed per cohort:
      helpful_rate     : fraction of feedback marked was_helpful=True
      avg_outcome_delta: average measured metric improvement after acting
      sample_count     : number of feedback rows in this cohort

    The "improvement" field is the delta in helpful_rate (post − pre):
      positive = recommendations got better after the weight update
      negative = recommendations got worse (or pre was already good)

    Returns
    -------
    {
      "project_id": int,
      "weight_updates_found": int,
      "categories": {
        category_name: {
          "weight_change_count": int,
          "first_update_at":     str (ISO),
          "last_update_at":      str (ISO),
          "pre_update":  { "helpful_rate": float, "avg_outcome_delta": float, "sample_count": int },
          "post_update": { "helpful_rate": float, "avg_outcome_delta": float, "sample_count": int },
          "improvement": float,   # post_helpful_rate - pre_helpful_rate
          "verdict":     str,     # 'improving' | 'neutral' | 'degrading'
        }
      }
    }
    """
    # 1. Find all self-learning weight-update events for this project.
    weight_events = (
        db.query(models.CategoryWeightHistory)
        .filter(
            models.CategoryWeightHistory.project_id == project_id,
            models.CategoryWeightHistory.source == "self_learning",
        )
        .order_by(models.CategoryWeightHistory.created_at)
        .all()
    )

    if not weight_events:
        return {
            "project_id": project_id,
            "weight_updates_found": 0,
            "message": (
                "No self-learning weight updates found for this project. "
                "Trigger POST /admin/self-learn/{project_id} first."
            ),
            "categories": {},
        }

    # 2. Group events by category and find the first update timestamp per category.
    from collections import defaultdict
    category_first_update: dict[str, object] = {}
    category_last_update:  dict[str, object] = {}
    category_event_count:  dict[str, int]    = defaultdict(int)

    for ev in weight_events:
        cat = ev.category
        category_event_count[cat] += 1
        if cat not in category_first_update:
            category_first_update[cat] = ev.created_at
        category_last_update[cat] = ev.created_at

    # 3. Pull all recommendations + feedback for this project.
    recs = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.project_id == project_id)
        .all()
    )
    rec_map = {r.id: r for r in recs}

    feedbacks = (
        db.query(models.RecommendationFeedback)
        .filter(models.RecommendationFeedback.recommendation_id.in_([r.id for r in recs]))
        .all()
    )

    # 4. For each feedback row, look up what category its recommendation relates to.
    #    We use the metric_name column (rich feedback) when available, otherwise
    #    fall through to the related_metrics join.
    def _get_category(fb) -> str | None:
        if fb.category:
            return fb.category
        rec = rec_map.get(fb.recommendation_id)
        if rec is None:
            return None
        for mid in (rec.related_metrics or []):
            defn = get_metric_definition(db, mid)
            if defn:
                return defn.category
        return None

    # 5. Split feedback into pre/post cohorts per category.
    pre:  dict[str, list] = defaultdict(list)
    post: dict[str, list] = defaultdict(list)

    for fb in feedbacks:
        cat = _get_category(fb)
        if cat not in category_first_update:
            continue
        cutoff = category_first_update[cat]
        fb_ts  = (
            getattr(fb, "feedback_at", None)
            or getattr(fb, "created_at", None)
        )
        if fb_ts is None:
            continue
        # Make both tz-aware for comparison
        from datetime import timezone as _tz
        if hasattr(fb_ts, "tzinfo") and fb_ts.tzinfo is None:
            fb_ts = fb_ts.replace(tzinfo=_tz.utc)
        if hasattr(cutoff, "tzinfo") and cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=_tz.utc)

        if fb_ts < cutoff:
            pre[cat].append(fb)
        else:
            post[cat].append(fb)

    def _cohort_stats(rows: list) -> dict:
        if not rows:
            return {"helpful_rate": None, "avg_outcome_delta": None, "sample_count": 0}
        helpful = sum(1 for r in rows if r.was_helpful)
        deltas  = [float(r.outcome_delta) for r in rows if r.outcome_delta is not None]
        return {
            "helpful_rate":     round(helpful / len(rows), 3),
            "avg_outcome_delta": round(sum(deltas) / len(deltas), 3) if deltas else None,
            "sample_count":     len(rows),
        }

    # 6. Assemble report.
    categories_report: dict = {}
    for cat in category_first_update:
        pre_stats  = _cohort_stats(pre.get(cat, []))
        post_stats = _cohort_stats(post.get(cat, []))

        pre_rate  = pre_stats["helpful_rate"]
        post_rate = post_stats["helpful_rate"]
        improvement = None
        verdict     = "insufficient_data"
        if pre_rate is not None and post_rate is not None:
            improvement = round(post_rate - pre_rate, 3)
            if improvement > 0.05:
                verdict = "improving"
            elif improvement < -0.05:
                verdict = "degrading"
            else:
                verdict = "neutral"

        categories_report[cat] = {
            "weight_change_count": category_event_count[cat],
            "first_update_at":     category_first_update[cat].isoformat() if hasattr(category_first_update[cat], "isoformat") else str(category_first_update[cat]),
            "last_update_at":      category_last_update[cat].isoformat() if hasattr(category_last_update[cat], "isoformat") else str(category_last_update[cat]),
            "pre_update":          pre_stats,
            "post_update":         post_stats,
            "improvement":         improvement,
            "verdict":             verdict,
        }

    return {
        "project_id":           project_id,
        "weight_updates_found": len(weight_events),
        "categories":           categories_report,
    }


# ---------- Metric Dependency Discovery (Pillar 3) ----------

def save_dependency_edges(db: Session, project_id: int, edges: list):
    """
    Persist discovered dependency edges into the metric_dependency_graph audit table.
    """
    saved_records = []
    for e in edges:
        # Accepts object or dict
        src = getattr(e, "source_metric", None) or e.get("source_metric_key") or e.get("source_metric")
        tgt = getattr(e, "target_metric", None) or e.get("target_metric_key") or e.get("target_metric")
        lag = getattr(e, "lag", None) if getattr(e, "lag", None) is not None else e.get("lag_periods", 0)
        corr = getattr(e, "correlation", None) or e.get("correlation", 0.0)
        n = getattr(e, "sample_size", None) or e.get("sample_size", 0)
        conf = getattr(e, "confidence", None) or e.get("confidence", "low")
        reason = getattr(e, "reason", None) or e.get("reason", "")

        db_edge = models.MetricDependencyGraph(
            project_id=project_id,
            source_metric_key=src,
            target_metric_key=tgt,
            lag_periods=lag,
            correlation=corr,
            sample_size=n,
            confidence=conf,
            reason=reason,
        )
        db.add(db_edge)
        saved_records.append(db_edge)

    db.commit()
    for r in saved_records:
        db.refresh(r)
    return saved_records


def get_latest_dependency_edges(db: Session, project_id: int):
    """
    Return the most recent learned dependency edges for a project, deduplicated by
    (source_metric_key, target_metric_key).
    """
    rows = (
        db.query(models.MetricDependencyGraph)
        .filter(models.MetricDependencyGraph.project_id == project_id)
        .order_by(desc(models.MetricDependencyGraph.discovered_at))
        .all()
    )

    latest_edges = []
    seen = set()
    for row in rows:
        pair = (row.source_metric_key, row.target_metric_key)
        if pair not in seen:
            seen.add(pair)
            latest_edges.append(row)

    return latest_edges


def get_metric_values_dataset(db: Session, project_id: int):
    """
    Returns time-series metric values grouped by metric key:
    { metric_key: [(recorded_at, value), ...] }
    """
    rows = (
        db.query(models.MetricValue, models.MetricDefinition)
        .join(models.MetricDefinition, models.MetricValue.metric_id == models.MetricDefinition.id)
        .filter(models.MetricValue.project_id == project_id)
        .order_by(models.MetricValue.recorded_at)
        .all()
    )

    series_map = {}
    for val, defn in rows:
        key = defn.key
        series_map.setdefault(key, []).append((val.recorded_at, float(val.value)))

    return series_map



# ---------- Feedback Analytics (for Dashboard) ----------

def get_all_feedback_analytics(
    db: Session,
    project_id: int | None = None,
    category: str | None = None,
    user_role: str | None = None,
):
    """
    Return enriched feedback rows, optionally filtered.
    Only rows with the extended analytics columns populated (i.e. from CSV seed
    or the rich feedback API) are considered useful for analytics.
    """
    q = db.query(models.RecommendationFeedback).filter(
        models.RecommendationFeedback.metric_name.isnot(None)
    )
    if project_id is not None:
        q = q.filter(models.RecommendationFeedback.project_id == project_id)
    if category:
        q = q.filter(models.RecommendationFeedback.category == category)
    if user_role:
        q = q.filter(models.RecommendationFeedback.user_role == user_role)
    return q.order_by(models.RecommendationFeedback.feedback_at).all()


def build_feedback_analytics_summary(
    db: Session,
    project_id: int | None = None,
    category: str | None = None,
    user_role: str | None = None,
) -> dict:
    """
    Compute all analytics aggregations in Python from the enriched feedback rows.
    Returns a dict matching the FeedbackAnalyticsSummary schema.
    """
    from collections import defaultdict

    rows = get_all_feedback_analytics(db, project_id=project_id, category=category, user_role=user_role)

    if not rows:
        return {
            "total_feedback": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "overall_helpfulness_rate": 0.0,
            "avg_priority_score": 0.0,
            "most_active_role": None,
            "critical_feedback_count": 0,
            "date_range_start": None,
            "date_range_end": None,
            "by_category": [],
            "by_role": [],
            "by_metric": [],
            "by_project": [],
            "daily_trends": [],
        }

    total = len(rows)
    helpful_count = sum(1 for r in rows if r.was_helpful)
    not_helpful_count = total - helpful_count
    priority_scores = [float(r.priority_score) for r in rows if r.priority_score is not None]
    avg_priority = sum(priority_scores) / len(priority_scores) if priority_scores else 0.0
    critical_count = sum(1 for r in rows if r.priority_score and float(r.priority_score) >= 60)

    feedback_ats = [r.feedback_at for r in rows if r.feedback_at]
    date_start = min(feedback_ats).strftime("%Y-%m-%d") if feedback_ats else None
    date_end   = max(feedback_ats).strftime("%Y-%m-%d") if feedback_ats else None

    # --- By category ---
    cat_buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "helpful": 0, "scores": []})
    for r in rows:
        cat = r.category or "unknown"
        cat_buckets[cat]["total"] += 1
        if r.was_helpful:
            cat_buckets[cat]["helpful"] += 1
        if r.priority_score is not None:
            cat_buckets[cat]["scores"].append(float(r.priority_score))

    by_category = [
        {
            "category": cat,
            "total": v["total"],
            "helpful": v["helpful"],
            "helpfulness_rate": round(v["helpful"] / v["total"] * 100, 1) if v["total"] else 0.0,
            "avg_priority_score": round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else 0.0,
        }
        for cat, v in sorted(cat_buckets.items())
    ]

    # --- By role ---
    role_buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "helpful": 0})
    for r in rows:
        role = r.user_role or "Unknown"
        role_buckets[role]["total"] += 1
        if r.was_helpful:
            role_buckets[role]["helpful"] += 1

    by_role = sorted(
        [
            {
                "user_role": role,
                "total": v["total"],
                "helpful": v["helpful"],
                "helpfulness_rate": round(v["helpful"] / v["total"] * 100, 1) if v["total"] else 0.0,
            }
            for role, v in role_buckets.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    most_active_role = by_role[0]["user_role"] if by_role else None

    # --- By metric ---
    metric_buckets: dict[str, dict] = defaultdict(
        lambda: {"category": "unknown", "total": 0, "helpful": 0, "scores": [], "devs": []}
    )
    for r in rows:
        name = r.metric_name or "Unknown"
        metric_buckets[name]["category"] = r.category or "unknown"
        metric_buckets[name]["total"] += 1
        if r.was_helpful:
            metric_buckets[name]["helpful"] += 1
        if r.priority_score is not None:
            metric_buckets[name]["scores"].append(float(r.priority_score))
        if r.deviation is not None:
            metric_buckets[name]["devs"].append(float(r.deviation))

    by_metric = sorted(
        [
            {
                "metric_name": name,
                "category": v["category"],
                "total": v["total"],
                "helpful": v["helpful"],
                "helpfulness_rate": round(v["helpful"] / v["total"] * 100, 1) if v["total"] else 0.0,
                "avg_priority_score": round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else 0.0,
                "avg_deviation": round(sum(v["devs"]) / len(v["devs"]), 3) if v["devs"] else 0.0,
            }
            for name, v in metric_buckets.items()
        ],
        key=lambda x: x["avg_priority_score"],
        reverse=True,
    )

    # --- By project ---
    proj_buckets: dict[int, dict] = defaultdict(lambda: {"total": 0, "helpful": 0})
    for r in rows:
        if r.project_id is not None:
            proj_buckets[r.project_id]["total"] += 1
            if r.was_helpful:
                proj_buckets[r.project_id]["helpful"] += 1

    by_project = sorted(
        [
            {
                "project_id": pid,
                "total": v["total"],
                "helpful": v["helpful"],
                "helpfulness_rate": round(v["helpful"] / v["total"] * 100, 1) if v["total"] else 0.0,
            }
            for pid, v in proj_buckets.items()
        ],
        key=lambda x: x["project_id"],
    )

    # --- Daily trends ---
    day_buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "helpful": 0})
    for r in rows:
        if r.feedback_at:
            day = r.feedback_at.strftime("%Y-%m-%d")
            day_buckets[day]["total"] += 1
            if r.was_helpful:
                day_buckets[day]["helpful"] += 1

    daily_trends = [
        {
            "date": day,
            "total": v["total"],
            "helpful": v["helpful"],
            "helpfulness_rate": round(v["helpful"] / v["total"] * 100, 1) if v["total"] else 0.0,
        }
        for day, v in sorted(day_buckets.items())
    ]

    return {
        "total_feedback": total,
        "helpful_count": helpful_count,
        "not_helpful_count": not_helpful_count,
        "overall_helpfulness_rate": round(helpful_count / total * 100, 1) if total else 0.0,
        "avg_priority_score": round(avg_priority, 1),
        "most_active_role": most_active_role,
        "critical_feedback_count": critical_count,
        "date_range_start": date_start,
        "date_range_end": date_end,
        "by_category": by_category,
        "by_role": by_role,
        "by_metric": by_metric,
        "by_project": by_project,
        "daily_trends": daily_trends,
    }


# ---------- Metric Dependency Discovery (Pillar 3) ----------

def save_dependency_edges(db: Session, project_id: int, edges: list):
    """
    Persist discovered dependency edges into the metric_dependency_graph audit table.
    """
    saved_records = []
    for e in edges:
        # Accepts object or dict
        src = getattr(e, "source_metric", None) or e.get("source_metric_key") or e.get("source_metric")
        tgt = getattr(e, "target_metric", None) or e.get("target_metric_key") or e.get("target_metric")
        lag = getattr(e, "lag", None) if getattr(e, "lag", None) is not None else e.get("lag_periods", 0)
        corr = getattr(e, "correlation", None) or e.get("correlation", 0.0)
        n = getattr(e, "sample_size", None) or e.get("sample_size", 0)
        conf = getattr(e, "confidence", None) or e.get("confidence", "low")
        reason = getattr(e, "reason", None) or e.get("reason", "")

        db_edge = models.MetricDependencyGraph(
            project_id=project_id,
            source_metric_key=src,
            target_metric_key=tgt,
            lag_periods=lag,
            correlation=corr,
            sample_size=n,
            confidence=conf,
            reason=reason,
        )
        db.add(db_edge)
        saved_records.append(db_edge)

    db.commit()
    for r in saved_records:
        db.refresh(r)
    return saved_records


def get_latest_dependency_edges(db: Session, project_id: int):
    """
    Return the most recent learned dependency edges for a project, deduplicated by
    (source_metric_key, target_metric_key).
    """
    rows = (
        db.query(models.MetricDependencyGraph)
        .filter(models.MetricDependencyGraph.project_id == project_id)
        .order_by(desc(models.MetricDependencyGraph.discovered_at))
        .all()
    )

    latest_edges = []
    seen = set()
    for row in rows:
        pair = (row.source_metric_key, row.target_metric_key)
        if pair not in seen:
            seen.add(pair)
            latest_edges.append(row)

    return latest_edges


def get_metric_values_dataset(db: Session, project_id: int):
    """
    Returns time-series metric values grouped by metric key:
    { metric_key: [(recorded_at, value), ...] }
    """
    rows = (
        db.query(models.MetricValue, models.MetricDefinition)
        .join(models.MetricDefinition, models.MetricValue.metric_id == models.MetricDefinition.id)
        .filter(models.MetricValue.project_id == project_id)
        .order_by(models.MetricValue.recorded_at)
        .all()
    )

    series_map = {}
    for val, defn in rows:
        key = defn.key
        series_map.setdefault(key, []).append((val.recorded_at, float(val.value)))

    return series_map

