from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


# ---------- Projects ----------

class ProjectCreate(BaseModel):
    name: str
    source: str
    external_id: str


class ProjectResponse(ProjectCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Metric Definitions ----------

class MetricDefinitionResponse(BaseModel):
    id: int
    key: str
    display_name: str
    category: str
    source: str
    unit: Optional[str] = None
    higher_is_better: bool
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Metric Values ----------

class MetricValueCreate(BaseModel):
    project_id: int
    metric_id: int
    value: float
    recorded_at: datetime
    raw_payload: Optional[Any] = None


class MetricValueResponse(BaseModel):
    id: int
    project_id: int
    metric_id: int
    value: float
    recorded_at: datetime
    collected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# A metric value enriched with its definition, for dashboard display
class MetricValueWithDefinition(BaseModel):
    id: int
    metric_key: str
    display_name: str
    category: str
    unit: Optional[str] = None
    higher_is_better: bool
    value: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# ---------- Recommendations ----------

class RecommendationResponse(BaseModel):
    id: int
    project_id: int
    title: str
    explanation: str
    priority_score: float
    related_metrics: Optional[List[int]] = None
    status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecommendationStatusUpdate(BaseModel):
    status: str  # open | acknowledged | actioned | dismissed


# ---------- Feedback ----------

class FeedbackCreate(BaseModel):
    recommendation_id: int
    was_helpful: bool
    user_comment: Optional[str] = None
    outcome_metric_id: Optional[int] = None
    outcome_delta: Optional[float] = None


class FeedbackResponse(FeedbackCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Feedback Analytics ----------

class FeedbackAnalyticsRow(BaseModel):
    id: int
    project_id: Optional[int] = None
    recommendation_id: int
    metric_id: Optional[int] = None
    metric_name: Optional[str] = None
    category: Optional[str] = None
    actual_value: Optional[float] = None
    target_value: Optional[float] = None
    deviation: Optional[float] = None
    severity: Optional[float] = None
    priority_score: Optional[float] = None
    was_helpful: Optional[bool] = None
    user_role: Optional[str] = None
    feedback_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CategoryBreakdown(BaseModel):
    category: str
    total: int
    helpful: int
    helpfulness_rate: float
    avg_priority_score: float


class RoleBreakdown(BaseModel):
    user_role: str
    total: int
    helpful: int
    helpfulness_rate: float


class MetricBreakdown(BaseModel):
    metric_name: str
    category: str
    total: int
    helpful: int
    helpfulness_rate: float
    avg_priority_score: float
    avg_deviation: float


class ProjectBreakdown(BaseModel):
    project_id: int
    total: int
    helpful: int
    helpfulness_rate: float


class DailyTrend(BaseModel):
    date: str          # "YYYY-MM-DD"
    total: int
    helpful: int
    helpfulness_rate: float


class FeedbackAnalyticsSummary(BaseModel):
    total_feedback: int
    helpful_count: int
    not_helpful_count: int
    overall_helpfulness_rate: float
    avg_priority_score: float
    most_active_role: Optional[str] = None
    critical_feedback_count: int        # rows where priority_score >= 60
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    by_category: List[CategoryBreakdown] = []
    by_role: List[RoleBreakdown] = []
    by_metric: List[MetricBreakdown] = []
    by_project: List[ProjectBreakdown] = []
    daily_trends: List[DailyTrend] = []


# ---------- Risk Profile ----------

class RiskProfileCreate(BaseModel):
    team_size: Optional[int] = None
    tech_debt_index: Optional[float] = 0.5   # 0.0 (clean) to 1.0 (severe debt)
    risk_tolerance: Optional[str] = "medium" # low | medium | high
    deployment_env: Optional[str] = None     # cloud | on-prem | hybrid
    notes: Optional[str] = None


class RiskProfileResponse(RiskProfileCreate):
    id: int
    project_id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Weight History ----------

class WeightHistoryResponse(BaseModel):
    id: int
    project_id: int
    category: str
    old_weight: float
    new_weight: float
    source: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Enriched Recommendation (multi-agent output) ----------

class AgentStep(BaseModel):
    """One named agent's contribution logged in the provenance trail."""
    agent: str            # e.g. "Perceiver", "AdaptiveWeighter", "Negotiator"
    action: str           # short human-readable description of what it did
    detail: Optional[str] = None  # optional longer note


class EnrichedRecommendationResponse(BaseModel):
    """
    Full multi-agent pipeline output per recommendation.
    Extends the basic response with agent provenance and adaptive weights used.
    """
    id: int
    project_id: int
    title: str
    explanation: str
    priority_score: float
    related_metrics: Optional[List[int]] = None
    status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Multi-agent enrichments
    reasoning_trail: List[str] = []           # per-line trail with [AgentName] prefixes
    agent_trail: List[AgentStep] = []         # structured provenance log across all agents
    adaptive_weights: Optional[dict] = None   # weights used in this pipeline run
    trend_slope: Optional[float] = None       # metric trend slope (+ = worsening)
    conflict_note: Optional[str] = None       # set by Negotiator when a penalty was applied
    detected_domain: Optional[str] = None     # banking | healthcare | gaming | ecommerce | general
    confidence_score: float = 0.0             # 0.0 to 1.0 confidence score
    confidence_label: str = "low"             # high | medium | low
    confidence_evidence: List[str] = []       # evidence breakdown list
    ai_narrated: bool = False

    class Config:
        from_attributes = True


# ---------- Metric Dependency Discovery (Pillar 3) ----------

class DependencyEdgeResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    source_metric_key: str
    target_metric_key: str
    lag_periods: int = 0
    correlation: float
    sample_size: int
    confidence: str
    reason: Optional[str] = None
    discovered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DependencyDiscoveryResponse(BaseModel):
    status: str
    project_id: int
    edges_discovered: int
    edges: List[DependencyEdgeResponse]
    summary: str


# ---------- Bayesian & Causal Graph Schemas ----------

class BayesianWeightState(BaseModel):
    weight: float
    confidence: float
    sample_count: float
    trend: str
    alpha: float
    beta: float
    alpha0: float
    beta0: float
    domain_context: Optional[str] = None


class CausalEdgeResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    source_metric: str
    target_metric: str
    edge_strength: float
    causal_confidence: float
    effect_type: str
    evidence_type: str
    competing_hypotheses: int = 0
    confirmations: int = 0
    refutations: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    evolution_log: Optional[str] = None

    class Config:
        from_attributes = True


class ContextMemoryResponse(BaseModel):
    id: Optional[int] = None
    context_key: str
    metric_name: str
    learned_alpha0: float
    learned_beta0: float
    predictiveness: float
    outcome_correlation: Optional[float] = None
    project_count: int
    avg_outcome: Optional[float] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoalConstraintCreate(BaseModel):
    constraint_type: str  # risk_budget | cost_limit | time_limit
    constraint_value: float


class GoalConstraintResponse(GoalConstraintCreate):
    id: int
    project_id: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True



