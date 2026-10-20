from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric, TIMESTAMP,
    ForeignKey, ARRAY, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    source = Column(String(50), nullable=False)       # azure_devops | github | sonarqube
    external_id = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)      # code_quality | process | devops
    source = Column(String(50), nullable=False)
    unit = Column(String(50))
    higher_is_better = Column(Boolean, default=True)
    description = Column(Text)


class MetricValue(Base):
    __tablename__ = "metric_values"

    id = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False)
    value = Column(Numeric, nullable=False)
    recorded_at = Column(TIMESTAMP, nullable=False)
    collected_at = Column(TIMESTAMP, server_default=func.now())
    raw_payload = Column(JSONB)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    priority_score = Column(Numeric, nullable=False)
    related_metrics = Column(ARRAY(Integer))
    status = Column(String(50), default="open")        # open | acknowledged | actioned | dismissed
    created_at = Column(TIMESTAMP, server_default=func.now())
    resolved_at = Column(TIMESTAMP, nullable=True)


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(BigInteger, ForeignKey("recommendations.id"), nullable=False)
    was_helpful = Column(Boolean)
    user_comment = Column(Text)
    outcome_metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=True)
    outcome_delta = Column(Numeric, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # --- Extended analytics columns (populated by CSV seed / rich feedback API) ---
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=True)
    metric_name = Column(String(255), nullable=True)
    category = Column(String(50), nullable=True)      # code_quality | process | devops
    actual_value = Column(Numeric, nullable=True)
    target_value = Column(Numeric, nullable=True)
    deviation = Column(Numeric, nullable=True)
    severity = Column(Numeric, nullable=True)
    priority_score = Column(Numeric, nullable=True)
    user_role = Column(String(100), nullable=True)    # Developer | QA Engineer | SRE | ...
    feedback_at = Column(TIMESTAMP, nullable=True)    # timestamp from the CSV / submission


class ProjectRiskProfile(Base):
    """Per-project context used by the adaptive weighting engine."""
    __tablename__ = "project_risk_profiles"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    team_size = Column(Integer, nullable=True)
    tech_debt_index = Column(Numeric(4, 3), default=0.5)   # 0.0 (clean) – 1.0 (severe)
    risk_tolerance = Column(String(20), default="medium")  # low | medium | high
    deployment_env = Column(String(50), nullable=True)     # cloud | on-prem | hybrid
    domain         = Column(String(50), nullable=True)     # banking | healthcare | gaming | ecommerce | general
    notes          = Column(Text, nullable=True)
    updated_at     = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class CategoryWeightHistory(Base):
    """Append-only audit ledger of every category weight change."""
    __tablename__ = "category_weight_history"

    id = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    category = Column(String(50), nullable=False)           # code_quality | process | devops
    old_weight = Column(Numeric(6, 4), nullable=False)
    new_weight = Column(Numeric(6, 4), nullable=False)
    source = Column(String(50), default="manual")           # manual | self_learning
    reason = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class MetricDependencyGraph(Base):
    """
    Append-only audit ledger of discovered metric-to-metric dependency edges
    (Pillar 3 — Metric Dependency Discovery).

    Every discovery run appends new rows; rows are never overwritten.
    This mirrors the audit-trail pattern of category_weight_history:
    the full evolution of the dependency graph is reproducible from this
    table alone.
    """
    __tablename__ = "metric_dependency_graph"

    id                = Column(BigInteger, primary_key=True, index=True)
    project_id        = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_metric_key = Column(String(100), nullable=False)
    target_metric_key = Column(String(100), nullable=False)
    lag_periods       = Column(Integer, nullable=False, default=0)
    # NUMERIC(5,4): 5 total digits, 4 decimal places → [-9.9999 … 9.9999]
    # Covers all valid Pearson r values in [-1, +1] with headroom.
    correlation       = Column(Numeric(5, 4), nullable=False)
    sample_size       = Column(Integer, nullable=False)
    confidence        = Column(String(20), nullable=False)   # high | medium | low
    reason            = Column(Text, nullable=True)
    discovered_at     = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # Composite index matching the DDL spec — accelerates
    # crud.get_latest_dependency_edges (queries by project, deduplicates
    # by target, ordered by most-recent discovered_at).
    __table_args__ = (
        Index(
            "idx_dependency_graph_project_target",
            "project_id", "target_metric_key", "discovered_at",
        ),
    )


class MetricWeight(Base):
    """
    Per-metric learning state table (v3 — metric_weights).

    Unlike CategoryWeightHistory (append-only audit ledger), this table is
    UPSERTED: it always holds the CURRENT learning state for each
    (project_id, metric_name) pair.

    Fields
    ------
    weight       : Multiplicative factor applied on top of category weight during
                   scoring.  Starts at 1.0 (neutral / no adjustment).
    confidence   : 0–1 fraction of confidence_sample_target reached.
                   Distinguishes "weight=1.4 from 500 samples" vs "from 10 samples".
    sample_count : Decay-weighted total of feedback samples seen (float because
                   exponential decay makes it non-integer).
    trend        : Direction the weight is moving — 'increasing' | 'decreasing' | 'stable'.
    last_updated : When the self-learning engine last wrote this row.
    """
    __tablename__ = "metric_weights"

    id           = Column(BigInteger, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_name  = Column(String(255), nullable=False)     # matches metric_definitions.key
    weight       = Column(Numeric(8, 4), nullable=False, default=1.0)
    confidence   = Column(Numeric(5, 4), nullable=False, default=0.0)  # 0=uninformed, 1=max confident
    sample_count = Column(Numeric(10, 4), nullable=False, default=0.0) # decay-weighted sample sum
    trend        = Column(String(20), nullable=False, default="stable") # increasing|decreasing|stable
    last_updated = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    alpha          = Column(Numeric(10, 4), nullable=False, default=5.0)
    beta           = Column(Numeric(10, 4), nullable=False, default=5.0)
    alpha0         = Column(Numeric(10, 4), nullable=False, default=5.0)
    beta0          = Column(Numeric(10, 4), nullable=False, default=5.0)
    domain_context = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_metric_weights_project", "project_id"),
        {"extend_existing": True},
    )


class CausalEdge(Base):
    """Self-evolving causal dependency edge with confidence and evidence tracking."""
    __tablename__ = "causal_edges"

    id                  = Column(BigInteger, primary_key=True, index=True)
    project_id          = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_metric       = Column(String(100), nullable=False)
    target_metric       = Column(String(100), nullable=False)
    edge_strength       = Column(Numeric(6, 4), nullable=False, default=0.5)
    causal_confidence   = Column(Numeric(6, 4), nullable=False, default=0.0)
    effect_type         = Column(String(20), nullable=False, default="unknown") # 'direct' | 'indirect' | 'unknown'
    evidence_type       = Column(String(30), nullable=False, default="correlation") # 'correlation' | 'intervention' | 'temporal_precedence' | 'competing_rejected'
    competing_hypotheses = Column(Integer, nullable=False, default=0)
    confirmations       = Column(Integer, nullable=False, default=0)
    refutations         = Column(Integer, nullable=False, default=0)
    is_active           = Column(Boolean, nullable=False, default=True)
    created_at          = Column(TIMESTAMP, server_default=func.now())
    last_validated_at   = Column(TIMESTAMP, nullable=True)
    evolution_log       = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_causal_edges_project", "project_id", "is_active"),
        {"extend_existing": True},
    )


class ContextMemory(Base):
    """Learned priors and metric predictiveness from historical project outcomes."""
    __tablename__ = "context_memory"

    id                  = Column(BigInteger, primary_key=True, index=True)
    context_key         = Column(String(255), nullable=False)
    metric_name         = Column(String(255), nullable=False)
    learned_alpha0      = Column(Numeric(10, 4), nullable=False, default=5.0)
    learned_beta0       = Column(Numeric(10, 4), nullable=False, default=5.0)
    predictiveness      = Column(Numeric(6, 4), nullable=False, default=0.5)
    outcome_correlation = Column(Numeric(6, 4), nullable=True)
    project_count       = Column(Integer, nullable=False, default=0)
    avg_outcome         = Column(Numeric(8, 4), nullable=True)
    last_updated        = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_context_memory_key", "context_key", "metric_name"),
        {"extend_existing": True},
    )


class GoalConstraint(Base):
    """User-defined optimization constraints per project."""
    __tablename__ = "goal_constraints"

    id               = Column(BigInteger, primary_key=True, index=True)
    project_id       = Column(Integer, ForeignKey("projects.id"), nullable=False)
    constraint_type  = Column(String(50), nullable=False)  # risk_budget | cost_limit | time_limit
    constraint_value = Column(Numeric(10, 4), nullable=False)
    is_active        = Column(Boolean, nullable=False, default=True)
    created_at       = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_goal_constraints_project", "project_id", "is_active"),
        {"extend_existing": True},
    )


class HealthSnapshot(Base):
    """Historical project health score snapshots for trend evaluation."""
    __tablename__ = "health_snapshots"

    id                 = Column(BigInteger, primary_key=True, index=True)
    project_id         = Column(Integer, ForeignKey("projects.id"), nullable=False)
    overall_score      = Column(Numeric(6, 2), nullable=False)
    code_quality_score = Column(Numeric(6, 2), nullable=False)
    process_score      = Column(Numeric(6, 2), nullable=False)
    devops_score       = Column(Numeric(6, 2), nullable=False)
    ai_risk_score      = Column(Numeric(6, 2), nullable=False)
    status_trend       = Column(String(20), default="stable")  # improving | stable | declining
    created_at         = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_health_snapshots_project", "project_id", "created_at"),
        {"extend_existing": True},
    )


class Anomaly(Base):
    """Detected metric anomalies."""
    __tablename__ = "anomalies"

    id                 = Column(BigInteger, primary_key=True, index=True)
    project_id         = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_key         = Column(String(100), nullable=False)
    metric_name        = Column(String(255), nullable=False)
    current_value      = Column(Numeric(10, 4), nullable=False)
    expected_min       = Column(Numeric(10, 4), nullable=False)
    expected_max       = Column(Numeric(10, 4), nullable=False)
    deviation_pct      = Column(Numeric(6, 2), nullable=False)
    severity           = Column(String(20), nullable=False)   # critical | warning | info
    possible_cause     = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    is_acknowledged    = Column(Boolean, default=False)
    detected_at        = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_anomalies_project", "project_id", "detected_at"),
        {"extend_existing": True},
    )


class RecommendationAction(Base):
    """Audit log of actions/interventions taken on recommendations."""
    __tablename__ = "recommendation_actions"

    id                = Column(BigInteger, primary_key=True, index=True)
    recommendation_id = Column(BigInteger, ForeignKey("recommendations.id"), nullable=False)
    action_type       = Column(String(50), nullable=False)  # start | resolve | verify | dismiss
    notes             = Column(Text, nullable=True)
    created_at        = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_rec_actions_rec", "recommendation_id"),
        {"extend_existing": True},
    )


class RecommendationOutcome(Base):
    """Automated before/after verification result for resolved recommendations."""
    __tablename__ = "recommendation_outcomes"

    id                = Column(BigInteger, primary_key=True, index=True)
    recommendation_id = Column(BigInteger, ForeignKey("recommendations.id"), nullable=False)
    project_id        = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_key        = Column(String(100), nullable=False)
    before_value      = Column(Numeric(10, 4), nullable=False)
    after_value       = Column(Numeric(10, 4), nullable=False)
    improvement_pct   = Column(Numeric(6, 2), nullable=False)
    goal_achieved     = Column(Boolean, nullable=False)
    measured_at       = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_rec_outcomes_rec", "recommendation_id"),
        {"extend_existing": True},
    )


class ProjectEvent(Base):
    """Project timeline events feed."""
    __tablename__ = "project_events"

    id            = Column(BigInteger, primary_key=True, index=True)
    project_id    = Column(Integer, ForeignKey("projects.id"), nullable=False)
    event_type    = Column(String(50), nullable=False)  # metric_degraded | metric_improved | rec_generated | rec_resolved | anomaly | deployment | commit | pr | ai_intervention
    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at    = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_project_events_project", "project_id", "created_at"),
        {"extend_existing": True},
    )


class Alert(Base):
    """Alerts generated for critical deviations, health changes, and anomalies."""
    __tablename__ = "alerts"

    id         = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)   # critical | warning | info | improvement
    title      = Column(String(255), nullable=False)
    message    = Column(Text, nullable=False)
    is_read    = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_alerts_project", "project_id", "is_read"),
        {"extend_existing": True},
    )


class RiskPrediction(Base):
    """Predictive risk analysis records."""
    __tablename__ = "risk_predictions"

    id                   = Column(BigInteger, primary_key=True, index=True)
    project_id           = Column(Integer, ForeignKey("projects.id"), nullable=False)
    risk_category        = Column(String(50), nullable=False)  # deployment_failure | incident_risk | tech_debt | quality_degradation | delivery_slowdown
    risk_level           = Column(String(20), nullable=False)  # critical | high | medium | low
    probability          = Column(Numeric(5, 4), nullable=False)  # 0.0 to 1.0
    affected_metric      = Column(String(100), nullable=False)
    reason               = Column(Text, nullable=False)
    confidence           = Column(Numeric(5, 4), nullable=False)
    recommended_mitigation = Column(Text, nullable=True)
    created_at           = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_risk_predictions_project", "project_id", "created_at"),
        {"extend_existing": True},
    )


class MLModelRegistry(Base):
    """Model registry tracking trained models, algorithms, and evaluation metrics."""
    __tablename__ = "ml_model_registry"

    id                 = Column(Integer, primary_key=True, index=True)
    model_id           = Column(String(100), unique=True, nullable=False, index=True)
    name               = Column(String(255), nullable=False)
    category           = Column(String(50), nullable=False)   # code_quality | process | devops
    algorithm          = Column(String(100), nullable=False)  # random_forest | xgboost | isolation_forest | arima
    target_metric      = Column(String(100), nullable=False)
    version            = Column(String(20), nullable=False, default="1.0.0")
    status             = Column(String(50), nullable=False, default="ready") # ready | training | degraded
    hyperparameters    = Column(JSONB, nullable=True)
    features           = Column(JSONB, nullable=True)
    evaluation_metrics = Column(JSONB, nullable=True)         # mae, rmse, r2, f1, roc_auc, etc.
    artifact_path      = Column(String(255), nullable=True)
    created_at         = Column(TIMESTAMP, server_default=func.now())
    updated_at         = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_ml_registry_cat", "category", "status"),
        {"extend_existing": True},
    )


class MLTrainingRun(Base):
    """Audit log of ML training runs and dataset splits."""
    __tablename__ = "ml_training_runs"

    id            = Column(BigInteger, primary_key=True, index=True)
    model_id      = Column(String(100), nullable=False, index=True)
    project_id    = Column(Integer, ForeignKey("projects.id"), nullable=True)
    status        = Column(String(50), nullable=False)   # success | failed | running
    train_samples = Column(Integer, nullable=False, default=0)
    test_samples  = Column(Integer, nullable=False, default=0)
    metrics_json  = Column(JSONB, nullable=True)
    duration_ms   = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at    = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_ml_training_runs_model", "model_id", "created_at"),
        {"extend_existing": True},
    )


class MLPrediction(Base):
    """Persisted predictions with intervals, confidence, and feature contributions."""
    __tablename__ = "ml_predictions"

    id                    = Column(BigInteger, primary_key=True, index=True)
    project_id            = Column(Integer, ForeignKey("projects.id"), nullable=False)
    model_id              = Column(String(100), nullable=False)
    category              = Column(String(50), nullable=False)
    target_metric         = Column(String(100), nullable=False)
    current_value         = Column(Numeric(10, 4), nullable=True)
    predicted_value       = Column(Numeric(10, 4), nullable=False)
    horizon               = Column(String(50), default="next_cycle")
    lower_bound           = Column(Numeric(10, 4), nullable=True)
    upper_bound           = Column(Numeric(10, 4), nullable=True)
    confidence            = Column(Numeric(5, 4), default=0.85)
    risk_level            = Column(String(20), default="low") # low | medium | high | critical
    feature_contributions = Column(JSONB, nullable=True)
    created_at            = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_ml_predictions_project_metric", "project_id", "target_metric", "created_at"),
        {"extend_existing": True},
    )


class MLCodeModule(Base):
    """Module-level risk assessments, complexity, churn, and smell breakdown."""
    __tablename__ = "ml_code_modules"

    id                = Column(BigInteger, primary_key=True, index=True)
    project_id        = Column(Integer, ForeignKey("projects.id"), nullable=False)
    module_name       = Column(String(255), nullable=False)
    file_path         = Column(String(500), nullable=True)
    churn_pct         = Column(Numeric(6, 2), default=0.0)
    complexity        = Column(Numeric(8, 2), default=0.0)
    coverage_pct      = Column(Numeric(6, 2), default=0.0)
    code_smells       = Column(Integer, default=0)
    defect_risk_level = Column(String(20), default="low") # low | medium | high
    defect_risk_prob  = Column(Numeric(5, 4), default=0.0)
    top_contributor   = Column(String(100), nullable=True)
    updated_at        = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_ml_code_modules_proj_risk", "project_id", "defect_risk_level"),
        {"extend_existing": True},
    )


class MLDriftStatus(Base):
    """Model and feature drift monitoring records."""
    __tablename__ = "ml_drift_status"

    id             = Column(BigInteger, primary_key=True, index=True)
    project_id     = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_key     = Column(String(100), nullable=False)
    baseline_mean  = Column(Numeric(10, 4), nullable=False)
    current_mean   = Column(Numeric(10, 4), nullable=False)
    drift_detected = Column(Boolean, default=False)
    p_value        = Column(Numeric(6, 4), nullable=True)
    drift_score    = Column(Numeric(6, 4), nullable=True)
    status         = Column(String(50), default="healthy") # healthy | drift_warning | retrain_recommended
    checked_at     = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_ml_drift_project_time", "project_id", "checked_at"),
        {"extend_existing": True},
    )


