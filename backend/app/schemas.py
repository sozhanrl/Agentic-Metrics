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


class GithubImportRequest(BaseModel):
    repo_url: str
    token: Optional[str] = None



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
    In public disclosure mode, internal arbitration trails and raw Bayesian/graph fields are stripped.
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

    # Multi-agent & Public Safe enrichments
    reasoning_summary: Optional[str] = None   # public-safe concise summary
    reasoning_trail: List[str] = []           # sanitized or full trail
    agent_trail: List[AgentStep] = []         # empty in public disclosure mode
    adaptive_weights: Optional[dict] = None   # None in public disclosure mode
    trend_slope: Optional[float] = None       # metric trend slope (+ = worsening)
    conflict_note: Optional[str] = None       # None in public disclosure mode
    detected_domain: Optional[str] = None     # None in public disclosure mode
    confidence_score: Optional[float] = None  # None in public disclosure mode
    confidence_label: str = "low"             # high | medium | low
    confidence_evidence: List[str] = []       # empty in public disclosure mode
    action_plan: Optional[dict] = None        # structured action plan
    ai_narrated: bool = False

    class Config:
        from_attributes = True



class GithubImportResponse(ProjectResponse):
    recommendations: List[EnrichedRecommendationResponse] = []
    ingested_metrics: List[str] = []
    skipped_metrics: List[str] = []


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


# ---------- Health Score Schemas ----------

class HealthSnapshotResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    overall_score: float
    code_quality_score: float
    process_score: float
    devops_score: float
    ai_risk_score: float
    status_trend: str
    previous_score: Optional[float] = None
    percentage_change: Optional[float] = None
    category_health: Optional[dict] = None
    key_drivers: list[str] = []
    top_strengths: list[str] = []
    top_weaknesses: list[str] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Anomaly Schemas ----------

class AnomalyResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    metric_key: str
    metric_name: str
    current_value: float
    expected_min: float
    expected_max: float
    deviation_pct: float
    severity: str
    possible_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    is_acknowledged: bool = False
    detected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Action Plan Schema ----------

class ActionPlanResponse(BaseModel):
    problem: str
    why_it_matters: str
    root_cause: str
    recommended_action: str
    expected_impact: str
    estimated_effort: str
    priority: str
    confidence_pct: int
    success_criteria: str


# ---------- Recommendation Lifecycle Schemas ----------

class RecommendationActionCreate(BaseModel):
    action_type: str  # start | resolve | verify | dismiss
    notes: Optional[str] = None


class RecommendationActionResponse(BaseModel):
    id: int
    recommendation_id: int
    action_type: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecommendationOutcomeResponse(BaseModel):
    id: Optional[int] = None
    recommendation_id: int
    project_id: int
    metric_key: str
    before_value: float
    after_value: float
    improvement_pct: float
    goal_achieved: bool
    measured_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Root Cause Analysis Schemas ----------

class CausalNodeResponse(BaseModel):
    metric_key: str
    display_name: str
    category: str
    current_value: float
    unit: str
    deviation_pct: float
    is_root_cause: bool
    relation_to_parent: Optional[str] = None
    edge_strength: float = 1.0
    confidence: float = 0.8
    evidence_type: str = "correlation"


class RootCauseResponse(BaseModel):
    target_metric: str
    target_display_name: str
    severity: str
    summary: str
    causal_chain: list[CausalNodeResponse] = []
    contributing_metrics: list[str] = []
    root_metric_key: Optional[str] = None
    root_metric_name: Optional[str] = None
    confidence_score: float = 0.0
    evidence_summary: str = ""
    system_impact: str = ""
    recommended_intervention: str = ""


# ---------- What-If Simulator Schemas ----------

class WhatIfRequest(BaseModel):
    simulated_values: dict[str, float]  # e.g. {"test_coverage": 80.0, "cycle_time": 3.0}


class SimulatedRecommendationDiffResponse(BaseModel):
    metric_key: str
    title: str
    baseline_priority: float
    simulated_priority: float
    priority_delta: float
    rank_before: int
    rank_after: int
    status: str


class WhatIfResponse(BaseModel):
    baseline_health: float
    predicted_health: float
    health_delta: float
    health_percentage_gain: float
    baseline_risk: float
    predicted_risk: float
    risk_delta: float
    affected_metrics: list[str]
    recommendation_diffs: list[SimulatedRecommendationDiffResponse]
    projected_category_health: dict
    simulation_notes: list[str]
    is_simulation: bool = True
    simulated_at: Optional[datetime] = None


# ---------- Risk Prediction Schemas ----------

class RiskItemResponse(BaseModel):
    risk_category: str
    title: str
    risk_level: str
    probability: float
    affected_metric: str
    reason: str
    confidence: float
    recommended_mitigation: Optional[str] = None
    has_sufficient_data: bool = True
    data_points_count: int = 0


class RiskPredictionReportResponse(BaseModel):
    overall_risk_level: str
    risks: list[RiskItemResponse] = []
    top_vulnerability: str = ""
    evaluated_at: Optional[datetime] = None


# ---------- Project Timeline Schemas ----------

class ProjectEventResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    event_type: str
    title: str
    description: Optional[str] = None
    metadata_json: Optional[Any] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Alert Schemas ----------

class AlertResponse(BaseModel):
    id: int
    project_id: int
    alert_type: str
    title: str
    message: str
    is_read: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Assistant Schemas ----------

class AssistantQuestionRequest(BaseModel):
    question: str


class AssistantResponseSchema(BaseModel):
    question: str
    answer: str
    evidence_points: list[str] = []
    suggested_followups: list[str] = []
    source_artifacts: list[str] = []
    responded_at: Optional[datetime] = None


# ---------- Team & GitHub Insights Schemas ----------

class ContributorActivity(BaseModel):
    login: str
    commits: int
    pull_requests: int
    lines_changed: int


class TeamInsightsResponse(BaseModel):
    project_id: int
    pr_throughput: float
    avg_pr_review_hours: float
    commit_activity_weekly: int
    avg_issue_resolution_days: float
    active_contributors_count: int
    workload_distribution: list[ContributorActivity] = []
    bottleneck_indicators: list[str] = []
    system_health_summary: str


class GitHubInsightsResponse(BaseModel):
    project_id: int
    open_prs_count: int
    closed_prs_count: int
    open_issues_count: int
    closed_issues_count: int
    commits_last_30_days: int
    avg_review_hours: float
    code_churn_pct: float
    recent_activity_feed: list[dict] = []


# ---------- Machine Learning Intelligence Schemas ----------

class MLModelResponse(BaseModel):
    id: int
    model_id: str
    name: str
    category: str
    algorithm: str
    target_metric: str
    version: str
    status: str
    hyperparameters: Optional[dict] = None
    features: Optional[list[str]] = None
    evaluation_metrics: Optional[dict] = None
    artifact_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MLPredictionResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    model_id: str
    category: str
    target_metric: str
    current_value: Optional[float] = None
    predicted_value: float
    horizon: str = "next_cycle"
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    confidence: float = 0.85
    risk_level: str = "low"
    feature_contributions: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MLCodeModuleResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    module_name: str
    file_path: Optional[str] = None
    churn_pct: float
    complexity: float
    coverage_pct: float
    code_smells: int
    defect_risk_level: str
    defect_risk_prob: float
    top_contributor: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MLDriftStatusResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    metric_key: str
    baseline_mean: float
    current_mean: float
    drift_detected: bool
    p_value: Optional[float] = None
    drift_score: Optional[float] = None
    status: str
    checked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MLStatusResponse(BaseModel):
    status: str
    ready: bool
    models_count: int
    algorithms: list[str]
    deep_learning_status: dict
    last_trained_at: Optional[datetime] = None


class MLTrainRequest(BaseModel):
    category: Optional[str] = None
    force: Optional[bool] = False


class MLPredictRequest(BaseModel):
    project_id: int
    category: str
    features: dict


# ---------- Dataset ML Endpoints ----------

class DatasetTrainRequest(BaseModel):
    datasets: Optional[list] = None  # ["defect", "trivial", "nontrivial"]
    force: Optional[bool] = False


class DefectPredictRequest(BaseModel):
    features: dict  # {LOC, CYCLO, LENGTH, VOLUME, DIFFICULTY, ...}
    model_name: Optional[str] = "auto"  # "auto", "random_forest", "xgboost", "logistic_regression"


class RefactoringPredictRequest(BaseModel):
    features: dict  # {cbo, wmc, dit, rfc, lcom, loc, ...}
    dataset_type: str = "trivial"  # "trivial" or "nontrivial"
    model_name: Optional[str] = "auto"




