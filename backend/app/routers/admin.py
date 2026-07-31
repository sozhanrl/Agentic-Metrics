"""
Admin Router — self-learning trigger and weight history endpoints.

These endpoints are intended for engineering managers / platform admins.
They are not needed for the core recommendation flow.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.agents.self_learner import compute_weight_updates
from app.agents.adaptive_weighter import compute_adaptive_weights
from app.agents.config import BASE_CATEGORY_WEIGHTS

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/self-learn/{project_id}")
def trigger_self_learning(project_id: int, db: Session = Depends(get_db)):
    """
    Trigger the self-learning weight update cycle for a project.

    1. Aggregates all feedback (category-level AND per-metric) with recency decay.
    2. Computes updated category weights and per-metric weights via the Bayesian
       update rule (confidence-scaled, outcome-blended, decay-weighted).
    3. Persists each category weight change to category_weight_history.
    4. Upserts per-metric learning state to metric_weights table.
    5. Returns before/after comparison, full update log, and per-metric weights.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Aggregate category-level feedback with recency decay.
    feedback_summary = crud.get_feedback_summary(db, project_id)

    # Aggregate per-metric feedback with recency decay.
    metric_feedback_summary = crud.get_feedback_summary_by_metric(db, project_id)

    if not feedback_summary and not metric_feedback_summary:
        return {
            "status": "no_feedback",
            "message": (
                "No feedback found for this project yet. Submit feedback via "
                "POST /feedback before triggering self-learning."
            ),
            "project_id": project_id,
        }

    # Load current category weights and per-metric weights.
    current_weights        = crud.get_latest_weights(db, project_id)
    current_metric_weights = crud.get_metric_weights(db, project_id)

    # Run the self-learning algorithm (v2: per-metric + confidence-scaled + decay).
    new_weights, update_log, new_metric_weights = compute_weight_updates(
        feedback_summary=feedback_summary,
        current_weights=current_weights,
        metric_feedback_summary=metric_feedback_summary,
        current_metric_weights=current_metric_weights,
    )

    # Persist each category weight change to the audit ledger.
    persisted_categories = []
    for entry in update_log:
        if (
            entry.get("level") == "category"
            and entry["action"] == "updated"
            and entry["new_weight"] != entry["old_weight"]
        ):
            crud.log_weight_event(
                db=db,
                project_id=project_id,
                category=entry["key"],
                old_weight=entry["old_weight"],
                new_weight=entry["new_weight"],
                source="self_learning",
                reason=entry.get("reason"),
            )
            persisted_categories.append(entry["key"])

    # Upsert per-metric learning state.
    persisted_metrics = []
    for metric_name, state in new_metric_weights.items():
        crud.upsert_metric_weight(
            db=db,
            project_id=project_id,
            metric_name=metric_name,
            weight=state["weight"],
            confidence=state["confidence"],
            sample_count=state["sample_count"],
            trend=state["trend"],
        )
        persisted_metrics.append(metric_name)

    return {
        "status":                  "ok",
        "project_id":              project_id,
        "weights_before":          current_weights,
        "weights_after":           new_weights,
        "categories_updated":      persisted_categories,
        "metrics_updated":         persisted_metrics,
        "update_log":              update_log,
        "metric_weights":          new_metric_weights,
        "feedback_summary":        feedback_summary,
        "metric_feedback_summary": metric_feedback_summary,
    }


@router.get("/weight-history/{project_id}", response_model=list[schemas.WeightHistoryResponse])
def get_weight_history(
    project_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Return the weight change audit ledger for a project, newest-first.
    Each entry records which category changed, from/to values, the source
    (manual or self_learning), and the reason string.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    history = crud.get_weight_history(db, project_id, limit=limit)
    return history


@router.get("/weights/current/{project_id}")
def get_current_weights(project_id: int, db: Session = Depends(get_db)):
    """
    Return the current effective weights for a project (latest history or base defaults).
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project_id,
        "weights":    crud.get_latest_weights(db, project_id),
    }


@router.get("/weights/compare/{project_id}")
def compare_weights(project_id: int, db: Session = Depends(get_db)):
    """
    Return all three weight tiers side-by-side for a project:

      base_prior       — The universal starting priors hardcoded in config.py.
                         These never change.
      self_learned     — The most recent weight per category that was written by
                         the self-learning agent (source='self_learning'). Falls
                         back to base_prior for any category not yet updated.
      adaptive_context — The result of running compute_adaptive_weights() against
                         the project's current risk profile. This is the per-run,
                         context-aware adjustment on top of self_learned.
      effective        — The same as adaptive_context; what the pipeline actually
                         used in the last run (self_learned → adaptive → score).

    This is the canonical "what did the agent learn vs. what did today's context
    adjust it to" comparison for presentations and audits.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ---- 1. Base prior -------------------------------------------------------
    base_prior = dict(BASE_CATEGORY_WEIGHTS)

    # ---- 2. Self-learned weights (source = 'self_learning' rows only) --------
    from app import models
    from sqlalchemy import desc as _desc
    self_learned = dict(base_prior)  # start from base so every category is represented
    rows = (
        db.query(models.CategoryWeightHistory)
        .filter(
            models.CategoryWeightHistory.project_id == project_id,
            models.CategoryWeightHistory.source == "self_learning",
        )
        .order_by(_desc(models.CategoryWeightHistory.created_at))
        .all()
    )
    seen: set = set()
    for row in rows:
        if row.category not in seen:
            self_learned[row.category] = float(row.new_weight)
            seen.add(row.category)

    # ---- 3. Adaptive context (risk-profile adjustments on top of self_learned) -
    risk_profile = crud.get_risk_profile(db, project_id)
    adaptive_context, steps = compute_adaptive_weights(
        base_weights=self_learned,
        risk_profile=risk_profile,
    )

    # ---- 4. Effective = adaptive context (what the pipeline uses) -----------
    effective = dict(adaptive_context)

    return {
        "project_id":       project_id,
        "base_prior":       base_prior,
        "self_learned":     self_learned,
        "adaptive_context": adaptive_context,
        "effective":        effective,
        "adaptive_steps":   steps,       # provenance trail for the adaptive adjustments
        "has_risk_profile": risk_profile is not None,
    }


# ---- Pillar 3: Metric Dependency Discovery Endpoints ----

@router.post("/discover-dependencies/{project_id}", response_model=schemas.DependencyDiscoveryResponse)
def discover_dependencies(project_id: int, db: Session = Depends(get_db)):
    """
    Trigger empirical Metric Dependency Discovery (Pillar 3) for a project.

    Pipeline
    --------
    1. Fetch all historical metric values for this project.
    2. Build values_df (project_id, metric_key, value, recorded_at) and
       metric_defs ({key: target/tolerance/higher_is_better}) — the exact
       inputs required by MetricDependencyDiscovery.discover().
    3. Run pairwise lead-lag Pearson correlation with lag 0-3 (weekly
       resampled severity series; see dependency_discovery.py for the full
       algorithm spec).
    4. Persist discovered edges to metric_dependency_graph ledger.
    5. Return learned graph edges with confidence labels and a summary.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from datetime import datetime, timezone
    import pandas as pd
    from app.agents.dependency_discovery import MetricDependencyDiscovery
    from app.agents.config import DEFAULT_TARGETS
    from app import models

    # ---- Build values_df ------------------------------------------------
    # Fetch all historical metric values joined with their definitions so
    # we can recover metric_key and higher_is_better in one pass.
    rows = (
        db.query(models.MetricValue, models.MetricDefinition)
        .join(models.MetricDefinition,
              models.MetricValue.metric_id == models.MetricDefinition.id)
        .filter(models.MetricValue.project_id == project_id)
        .order_by(models.MetricValue.recorded_at)
        .all()
    )

    if not rows:
        return {
            "status": "no_data",
            "project_id": project_id,
            "edges_discovered": 0,
            "edges": [],
            "summary": (
                "No metric history found for this project. "
                "Seed demo data first via POST /dev/seed/{project_id}."
            ),
        }

    df_records = [
        {
            "project_id":  val.project_id,
            "metric_key":  defn.key,
            "value":       float(val.value),
            "recorded_at": val.recorded_at,
        }
        for val, defn in rows
    ]
    values_df = pd.DataFrame(df_records)

    # ---- Build metric_defs ----------------------------------------------
    # Use DEFAULT_TARGETS from config for target/tolerance, and pull
    # higher_is_better from the metric definition ORM object.
    defn_hib_map = {defn.key: defn.higher_is_better for _, defn in rows}

    metric_defs: dict = {}
    for key in values_df["metric_key"].unique():
        defaults = DEFAULT_TARGETS.get(key, {"target": 1.0, "tolerance": 1.0})
        metric_defs[key] = {
            "target":           defaults["target"],
            "tolerance":        defaults["tolerance"],
            "higher_is_better": defn_hib_map.get(key, False),
        }

    # ---- Run discovery --------------------------------------------------
    as_of = datetime.now(timezone.utc).isoformat()
    engine = MetricDependencyDiscovery()
    discovered_edges = engine.discover(
        values_df, metric_defs, project_id=project_id, as_of=as_of
    )

    # ---- Persist edges --------------------------------------------------
    crud.save_dependency_edges(db, project_id, discovered_edges)
    latest_edges = crud.get_latest_dependency_edges(db, project_id)

    high_conf = sum(1 for e in discovered_edges if e.confidence == "high")
    fallback  = any("[domain-prior]" in (e.reason or "") for e in discovered_edges)
    method    = "domain-prior fallback" if fallback else "empirical Pearson lag-correlation"
    summary   = (
        f"Discovered {len(latest_edges)} dependency edge(s) via {method} "
        f"({high_conf} high-confidence)."
    )

    return {
        "status":          "ok",
        "project_id":      project_id,
        "edges_discovered": len(latest_edges),
        "edges":           latest_edges,
        "summary":         summary,
    }


@router.get("/dependencies/latest/{project_id}", response_model=list[schemas.DependencyEdgeResponse])
def get_latest_dependencies(project_id: int, db: Session = Depends(get_db)):
    """
    Return the latest learned metric dependency graph for a project.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return crud.get_latest_dependency_edges(db, project_id)


@router.get("/metric-weights/{project_id}")
def get_metric_weights(project_id: int, db: Session = Depends(get_db)):
    """
    Return the current per-metric learning state for a project.

    Each entry shows:
      weight       — multiplicative adjustment applied on top of category weight
      confidence   — 0–1 (fraction of confidence_sample_target reached)
      sample_count — decay-weighted total feedback samples
      trend        — 'increasing' | 'decreasing' | 'stable'

    This endpoint is the canonical view of what the self-learning engine has
    learned about individual metrics, as distinct from the category-level view
    returned by /admin/weights/current/{project_id}.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    weights = crud.get_metric_weights(db, project_id)
    return {
        "project_id":    project_id,
        "metric_weights": weights,
        "total_metrics":  len(weights),
    }


@router.get("/learning-validation/{project_id}")
def get_learning_validation(project_id: int, db: Session = Depends(get_db)):
    """
    Before/after comparison proving whether self-learning improved recommendations.

    Splits feedback into pre-update and post-update cohorts based on when the
    self-learning cycle ran.  Computes helpfulness_rate and avg_outcome_delta
    for each cohort, and returns an improvement delta per category.

    A positive improvement means recommendations issued after the weight update
    were acted on more helpfully than those issued before — direct evidence that
    the learning algorithm is getting smarter, not just changing numbers.

    Verdict:
      'improving'         — post_helpful_rate > pre_helpful_rate + 5pp
      'neutral'           — within ±5pp
      'degrading'         — post_helpful_rate < pre_helpful_rate - 5pp
      'insufficient_data' — one or both cohorts have no feedback yet
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return crud.get_learning_validation_report(db, project_id)
