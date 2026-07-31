"""
Central configuration for the multi-agent pipeline.

All constants previously scattered across recommendation_engine.py now live here,
so every agent reads from a single source of truth. Agents import from this module
rather than re-defining thresholds or weight priors locally.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Base category weights — the prior before adaptive adjustments and self-learning.
# Kept as a plain dict so they're JSON-serialisable and easy to copy/mutate.
# ---------------------------------------------------------------------------
BASE_CATEGORY_WEIGHTS: dict[str, float] = {
    "code_quality": 1.0,
    "process":      0.8,
    "devops":       1.1,
}

# ---------------------------------------------------------------------------
# Metric target definitions.
# Each entry: target  = "good" reference value
#             tolerance = slack band — deviation / tolerance = severity
# ---------------------------------------------------------------------------
DEFAULT_TARGETS: dict[str, dict] = {
    "code_churn":            {"target": 15,   "tolerance": 10},   # % lower-better
    "cyclomatic_complexity": {"target": 10,   "tolerance": 5},    # count lower-better
    "test_coverage":         {"target": 80,   "tolerance": 15},   # % higher-better
    "defect_density":        {"target": 1.0,  "tolerance": 0.75}, # defects/kloc lower-better
    "sprint_velocity":       {"target": 30,   "tolerance": 10},   # story pts higher-better
    "cycle_time":            {"target": 3,    "tolerance": 2},    # days lower-better
    "lead_time":             {"target": 7,    "tolerance": 4},    # days lower-better
    "deployment_frequency":  {"target": 3,    "tolerance": 2},    # per week higher-better
    "change_failure_rate":   {"target": 15,   "tolerance": 10},   # % lower-better
    "mttr":                  {"target": 4,    "tolerance": 3},    # hours lower-better
}

# ---------------------------------------------------------------------------
# Pipeline tuning knobs
# ---------------------------------------------------------------------------

# Minimum severity to surface a recommendation (below this = noise, skip it).
SEVERITY_THRESHOLD: float = 0.3

# Scale factor: severity 1.0 with weight 1.0 → this many priority points.
# Tuned so "right at the edge of tolerance" (severity=1) hits ~40-45 pts.
SCORE_SCALE: float = 40.0

# Trend amplification cap: worsening trend can boost severity by at most this fraction.
MAX_TREND_AMPLIFICATION: float = 0.6   # e.g. 0.5 severity * (1 + 0.6) = 0.8

# Number of history points the Perceiver uses for trend regression.
TREND_LOOKBACK: int = 6

# ---------------------------------------------------------------------------
# Conflict detection — metric pairs that share scarce developer capacity.
# When both members of a pair appear in the recommendation list, the
# Negotiator agent penalises the lower-priority one.
# ---------------------------------------------------------------------------
CONFLICT_PAIRS: list[tuple[str, str]] = [
    ("code_churn", "test_coverage"),         # both demand focused refactoring time
    ("cyclomatic_complexity", "test_coverage"),
    ("sprint_velocity", "cycle_time"),        # pushing velocity can inflate cycle time
    ("deployment_frequency", "change_failure_rate"),  # deploy more ↔ risk more failures
]

# Fractional priority penalty applied to the lower member of a conflict pair (0-1).
CONFLICT_PENALTY: float = 0.12   # 12% reduction

# ---------------------------------------------------------------------------
# Adaptive weighting — adjustment multipliers per risk-profile attribute.
# ---------------------------------------------------------------------------

# tech_debt_index buckets: low (<0.35) / medium (0.35-0.65) / high (>0.65)
TECH_DEBT_CODE_QUALITY_BOOST: dict[str, float] = {
    "low":    1.0,
    "medium": 1.15,
    "high":   1.35,
}

# risk_tolerance: low = tighten devops scrutiny; high = relax it
RISK_TOLERANCE_DEVOPS_FACTOR: dict[str, float] = {
    "low":    1.25,
    "medium": 1.0,
    "high":   0.85,
}

# small team (≤ 5) → process overhead hurts more, weight it lower
SMALL_TEAM_PROCESS_FACTOR: float = 0.75
SMALL_TEAM_THRESHOLD: int = 5

# ---------------------------------------------------------------------------
# Self-learning Bayesian nudge parameters
# ---------------------------------------------------------------------------

# How strongly feedback moves the needle per update cycle (learning rate).
SELF_LEARNING_RATE: float = 0.08

# Hard bounds: weights can never drift outside this range regardless of feedback.
WEIGHT_MIN: float = 0.3
WEIGHT_MAX: float = 2.0

# Minimum feedback samples required before self-learning applies a nudge.
MIN_FEEDBACK_SAMPLES: int = 3

# Confidence scaling: effective_rate = SELF_LEARNING_RATE * min(1, total / TARGET).
# A metric with fewer than this many decay-weighted samples is treated as
# low-confidence and moves the weight cautiously.
CONFIDENCE_SAMPLE_TARGET: int = 30

# Recency decay half-life for feedback age weighting (in days).
# feedback_weight = exp(-ln(2) / HALF_LIFE * days_ago)
# Global default; individual projects can override via project_settings.
FEEDBACK_DECAY_HALF_LIFE_DAYS: float = 60.0

# Per-project decay factor (0 < factor ≤ 1).  Each day without recent feedback
# multiplies by this factor.  Derived from FEEDBACK_DECAY_HALF_LIFE_DAYS via:
#   factor = 0.5 ** (1 / HALF_LIFE_DAYS)
# This constant is the DEFAULT; projects may store a custom factor in the DB.
DEFAULT_DECAY_FACTOR: float = 0.5 ** (1 / 60.0)  # ≈ 0.9885 per day

# ---------------------------------------------------------------------------
# Negotiator — graph-discount for empirically discovered causal edges
# ---------------------------------------------------------------------------

# When two recommendations share a discovered dependency edge (source → target),
# the downstream target metric is discounted to avoid double-counting a symptom
# and its root cause as two independent priorities.
GRAPH_DISCOUNT: float = 0.20   # 20% score reduction on the downstream symptom

# Maximum combined penalty a single recommendation can receive from stacking
# the graph-discount AND a static conflict-pair penalty.
# Example: graph=0.20 + conflict=0.12 = 0.32 → capped at 0.25.
MAX_TOTAL_PENALTY: float = 0.25


# ---------------------------------------------------------------------------
# Metric dependency graph (for Explainer agent reasoning trails).
# key → list of metric keys that are causally upstream of it.
# ---------------------------------------------------------------------------
METRIC_DEPENDENCIES: dict[str, list[str]] = {
    "defect_density":       ["test_coverage", "code_churn"],
    "cycle_time":           ["code_churn", "sprint_velocity"],
    "change_failure_rate":  ["test_coverage", "cyclomatic_complexity", "code_churn"],
    "mttr":                 ["deployment_frequency"],
    "lead_time":            ["cycle_time", "sprint_velocity"],
}


@dataclass
class AgentConfig:
    """
    Frozen snapshot of all configuration values for one pipeline run.
    Agents receive this object rather than reading module-level globals directly,
    making unit testing trivial (just pass a different config).
    """
    base_weights: dict[str, float]      = field(default_factory=lambda: dict(BASE_CATEGORY_WEIGHTS))
    default_targets: dict[str, dict]    = field(default_factory=lambda: dict(DEFAULT_TARGETS))
    severity_threshold: float           = SEVERITY_THRESHOLD
    score_scale: float                  = SCORE_SCALE
    max_trend_amplification: float      = MAX_TREND_AMPLIFICATION
    trend_lookback: int                 = TREND_LOOKBACK
    conflict_pairs: list                = field(default_factory=lambda: list(CONFLICT_PAIRS))
    conflict_penalty: float             = CONFLICT_PENALTY
    self_learning_rate: float           = SELF_LEARNING_RATE
    weight_min: float                   = WEIGHT_MIN
    weight_max: float                   = WEIGHT_MAX
    min_feedback_samples: int           = MIN_FEEDBACK_SAMPLES
    metric_dependencies: dict           = field(default_factory=lambda: dict(METRIC_DEPENDENCIES))
    # Confidence-scaled learning rate: ramps up from 0 as evidence accumulates.
    confidence_sample_target: int       = CONFIDENCE_SAMPLE_TARGET
    # Recency decay: half-life in days for feedback age weighting.
    feedback_decay_half_life_days: float = FEEDBACK_DECAY_HALF_LIFE_DAYS
    # Per-project override for decay factor (default is global constant).
    decay_factor: float                 = DEFAULT_DECAY_FACTOR
    # Negotiator graph-discount for empirically discovered causal dependencies.
    graph_discount: float               = GRAPH_DISCOUNT
    # Maximum combined penalty cap (graph + conflict) per recommendation.
    max_total_penalty: float            = MAX_TOTAL_PENALTY


def default_config() -> AgentConfig:
    """Returns a fresh AgentConfig with all module-level defaults."""
    return AgentConfig()
