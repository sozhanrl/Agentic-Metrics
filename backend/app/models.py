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

