"""
Core prioritization engine.

This is the "agentic reasoning" piece of the system: given the latest metric
values for a project, it decides WHICH issues matter most right now and
WHY, producing a ranked, explained list of recommendations rather than a
flat dashboard of numbers.

The reasoning is deliberately structured as an explicit pipeline
(perceive -> evaluate -> score -> explain) so every recommendation carries
a traceable "reasoning trail" the UI can render. That trail is what makes
this agentic rather than a static rules dashboard: every conclusion is
attributable to specific inputs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Category weights: how much a category matters to overall project health.
# These are the agent's starting priors; the feedback loop (recommendation
#_feedback table) is intended to adjust these over time based on which
# recommendations were actually acted on and helped.
CATEGORY_WEIGHTS = {
    "code_quality": 1.0,
    "process": 0.8,
    "devops": 1.1,
}

# Simple threshold model per metric key: (warning_ratio, critical_ratio)
# expressed as "how far from a reasonable target, in the bad direction".
# This is intentionally simple/explainable rather than a black box -
# swap for a learned model later without changing the pipeline shape.
DEFAULT_TARGETS = {
    "code_churn": {"target": 15, "tolerance": 10},          # % - lower better
    "cyclomatic_complexity": {"target": 10, "tolerance": 5},  # count - lower better
    "test_coverage": {"target": 80, "tolerance": 15},        # % - higher better
    "defect_density": {"target": 1.0, "tolerance": 0.75},    # defects/kloc - lower better
    "sprint_velocity": {"target": 30, "tolerance": 10},       # story points - higher better (stability matters more than value)
    "cycle_time": {"target": 3, "tolerance": 2},              # days - lower better
    "lead_time": {"target": 7, "tolerance": 4},               # days - lower better
    "deployment_frequency": {"target": 3, "tolerance": 2},    # per week - higher better
    "change_failure_rate": {"target": 15, "tolerance": 10},   # % - lower better
    "mttr": {"target": 4, "tolerance": 3},                    # hours - lower better
}


@dataclass
class MetricSignal:
    metric_id: int
    key: str
    display_name: str
    category: str
    unit: str | None
    higher_is_better: bool
    value: float
    recorded_at: datetime
    severity: float = 0.0        # 0 (fine) to 1+ (bad, can exceed 1 for critical)
    deviation_pct: float = 0.0   # how far from target, signed


@dataclass
class ScoredRecommendation:
    title: str
    explanation: str
    priority_score: float
    related_metric_ids: list[int]
    reasoning_trail: list[str] = field(default_factory=list)


def _evaluate_signal(key, display_name, category, unit, higher_is_better,
                      value, recorded_at, metric_id) -> MetricSignal:
    """Perceive step: turn a raw metric value into a severity signal."""
    signal = MetricSignal(
        metric_id=metric_id, key=key, display_name=display_name,
        category=category, unit=unit, higher_is_better=higher_is_better,
        value=value, recorded_at=recorded_at,
    )

    target_def = DEFAULT_TARGETS.get(key)
    if not target_def:
        return signal  # unknown metric, no scoring model - treat as neutral

    target = target_def["target"]
    tolerance = target_def["tolerance"]

    if higher_is_better:
        deviation = target - value  # positive = below target = bad
    else:
        deviation = value - target  # positive = above target = bad

    deviation_pct = (deviation / target) * 100 if target else 0
    severity = max(0.0, deviation / tolerance) if tolerance else 0.0

    signal.deviation_pct = round(deviation_pct, 1)
    signal.severity = round(severity, 2)
    return signal


def _score_signal(signal: MetricSignal) -> float:
    """Evaluate step: combine severity with category weight into a priority score (0-100)."""
    weight = CATEGORY_WEIGHTS.get(signal.category, 1.0)
    raw = signal.severity * weight * 40  # scale factor tuned so ~1 severity -> ~40-45 pts
    return round(min(raw, 100), 1)


def _explain_signal(signal: MetricSignal) -> tuple[str, str, list[str]]:
    """Explain step: turn the number into a human-readable title + reasoning trail."""
    direction = "below target" if signal.higher_is_better else "above target"
    unit = signal.unit or ""

    title = f"{signal.display_name} is {abs(signal.deviation_pct):.0f}% {direction}"

    trail = [
        f"Observed {signal.display_name}: {signal.value}{unit} (recorded {signal.recorded_at.date()})",
        f"Target for this metric: {DEFAULT_TARGETS.get(signal.key, {}).get('target', 'n/a')}{unit}",
        f"Deviation from target: {signal.deviation_pct:+.1f}%",
        f"Category weight applied ({signal.category}): x{CATEGORY_WEIGHTS.get(signal.category, 1.0)}",
        f"Resulting severity score: {signal.severity}",
    ]

    explanation = (
        f"{signal.display_name} is currently {signal.value}{unit}, "
        f"which is {abs(signal.deviation_pct):.0f}% {direction} "
        f"(target: {DEFAULT_TARGETS.get(signal.key, {}).get('target', 'n/a')}{unit}). "
        f"This falls in the '{signal.category.replace('_', ' ')}' category, "
        f"weighted x{CATEGORY_WEIGHTS.get(signal.category, 1.0)} in overall project health."
    )

    return title, explanation, trail


def generate_recommendations(metric_rows) -> list[ScoredRecommendation]:
    """
    Main agent pipeline entry point.

    metric_rows: list of (MetricValue, MetricDefinition) tuples, typically
    the latest value per metric for a project (see crud.get_latest_metric_values).

    Returns recommendations sorted by priority_score descending, highest first.
    Only metrics with severity > 0.3 (i.e. meaningfully off-target) produce
    a recommendation - we don't want to flood the user with noise for
    metrics that are merely a little off.
    """
    recommendations = []

    for value_row, definition in metric_rows:
        signal = _evaluate_signal(
            key=definition.key,
            display_name=definition.display_name,
            category=definition.category,
            unit=definition.unit,
            higher_is_better=definition.higher_is_better,
            value=float(value_row.value),
            recorded_at=value_row.recorded_at,
            metric_id=definition.id,
        )

        if signal.severity <= 0.3:
            continue  # not worth flagging

        score = _score_signal(signal)
        title, explanation, trail = _explain_signal(signal)

        recommendations.append(
            ScoredRecommendation(
                title=title,
                explanation=explanation,
                priority_score=score,
                related_metric_ids=[signal.metric_id],
                reasoning_trail=trail,
            )
        )

    recommendations.sort(key=lambda r: r.priority_score, reverse=True)
    return recommendations
