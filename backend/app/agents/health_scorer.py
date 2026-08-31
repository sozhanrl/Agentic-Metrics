"""
Project Health Scorer Agent — AI Software Engineering Intelligence Platform.

Calculates:
- Overall Health Score (0–100)
- Code Quality Score (0–100)
- Process Score (0–100)
- DevOps Score (0–100)
- AI Risk Score (0–100)
- Status Trend: 'improving' | 'stable' | 'declining'
- Health Breakdown and Insights

All scores are calculated dynamically from real metric values, deviations from targets,
category weights, and active recommendation severities — never fabricated or hardcoded.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
from app.agents.config import AgentConfig, default_config, DEFAULT_TARGETS, BASE_CATEGORY_WEIGHTS
from app.agents.perceiver import MetricSignal


@dataclass
class HealthScoreBreakdown:
    overall_score: float
    code_quality_score: float
    process_score: float
    devops_score: float
    ai_risk_score: float
    previous_score: Optional[float] = None
    percentage_change: Optional[float] = None
    status_trend: str = "stable"  # improving | stable | declining
    category_health: dict = field(default_factory=dict)
    key_drivers: list[str] = field(default_factory=list)
    top_strengths: list[str] = field(default_factory=list)
    top_weaknesses: list[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _calculate_metric_health(value: float, key: str, higher_is_better: bool, targets_dict: dict) -> float:
    """
    Calculate an individual metric's health score on a 0-100 scale based on target and tolerance.
    Score = 100 if at or better than target.
    Score drops toward 0 as deviation increases past tolerance.
    """
    target_def = targets_dict.get(key)
    if not target_def:
        return 75.0  # Unknown metric: default neutral healthy

    target = target_def["target"]
    tolerance = target_def["tolerance"]

    if higher_is_better:
        if value >= target:
            return 100.0
        gap = target - value
        # At target - tolerance -> score = 50. Beyond 2*tolerance -> 0.
        score = max(0.0, 100.0 - (gap / max(1e-6, tolerance)) * 50.0)
    else:
        if value <= target:
            return 100.0
        gap = value - target
        score = max(0.0, 100.0 - (gap / max(1e-6, tolerance)) * 50.0)

    return round(min(100.0, max(0.0, score)), 2)


def compute_health_score(
    signals: list[MetricSignal],
    recommendations: Optional[list] = None,
    previous_snapshot: Optional[Any] = None,
    adaptive_weights: Optional[dict] = None,
    cfg: Optional[AgentConfig] = None,
) -> HealthScoreBreakdown:
    """
    Compute full project health scores from current perceived metric signals.
    """
    cfg = cfg or default_config()
    targets = cfg.default_targets
    weights = adaptive_weights or dict(BASE_CATEGORY_WEIGHTS)

    if not signals:
        # No signals available
        return HealthScoreBreakdown(
            overall_score=0.0,
            code_quality_score=0.0,
            process_score=0.0,
            devops_score=0.0,
            ai_risk_score=0.0,
            status_trend="stable",
        )

    cat_scores = {"code_quality": [], "process": [], "devops": []}
    strengths = []
    weaknesses = []

    for s in signals:
        m_health = _calculate_metric_health(s.value, s.key, s.higher_is_better, targets)
        cat = s.category if s.category in cat_scores else "code_quality"
        cat_scores[cat].append((s.display_name, m_health, s.deviation_pct, s.severity))

        if m_health >= 85.0:
            strengths.append(f"{s.display_name} ({s.value}{s.unit or ''}) is performing strongly")
        elif s.severity > 0.4:
            weaknesses.append(f"{s.display_name} ({s.value}{s.unit or ''}) is deviating from target")

    # Category averages
    def _avg(items):
        if not items:
            return 80.0  # Neutral if category has no metrics yet
        return round(sum(item[1] for item in items) / len(items), 2)

    code_quality_score = _avg(cat_scores["code_quality"])
    process_score = _avg(cat_scores["process"])
    devops_score = _avg(cat_scores["devops"])

    # Weighted overall score
    w_cq = weights.get("code_quality", 1.0)
    w_pr = weights.get("process", 0.8)
    w_do = weights.get("devops", 1.1)
    tot_weight = w_cq + w_pr + w_do

    overall_score = round(
        (code_quality_score * w_cq + process_score * w_pr + devops_score * w_do) / max(1e-6, tot_weight),
        2
    )

    # AI Risk Score (0 = no risk, 100 = extreme risk)
    # Computed from open recommendations' priority scores and active worsening trends
    rec_risk = 0.0
    if recommendations:
        open_recs = [r for r in recommendations if getattr(r, "status", "") in ("open", "in_progress")]
        if open_recs:
            total_rec_prio = sum(float(getattr(r, "priority_score", 0.0)) for r in open_recs)
            rec_risk = min(80.0, total_rec_prio / len(open_recs) * 0.8)

    trend_worsening_count = sum(1 for s in signals if getattr(s, "trend_direction", "") == "worsening")
    trend_risk = min(20.0, trend_worsening_count * 5.0)

    # Invert overall health penalty to risk
    health_deficit = max(0.0, (100.0 - overall_score) * 0.4)
    ai_risk_score = round(min(100.0, max(0.0, health_deficit + rec_risk * 0.4 + trend_risk)), 2)

    # Compare with previous snapshot
    previous_score = None
    percentage_change = None
    status_trend = "stable"

    if previous_snapshot:
        prev_val = float(getattr(previous_snapshot, "overall_score", 0.0))
        previous_score = prev_val
        if prev_val > 0:
            percentage_change = round(((overall_score - prev_val) / prev_val) * 100.0, 2)
            if percentage_change > 1.5:
                status_trend = "improving"
            elif percentage_change < -1.5:
                status_trend = "declining"
            else:
                status_trend = "stable"

    # Key drivers
    key_drivers = []
    if overall_score < 70.0:
        worst_cat = min(
            [("Code Quality", code_quality_score), ("Process", process_score), ("DevOps", devops_score)],
            key=lambda x: x[1]
        )
        key_drivers.append(f"{worst_cat[0]} is the primary drag on project health ({worst_cat[1]} score)")
    if trend_worsening_count > 0:
        key_drivers.append(f"{trend_worsening_count} metric(s) currently exhibiting negative momentum")
    if not key_drivers:
        key_drivers.append("Project engineering metrics are within expected operating tolerances")

    return HealthScoreBreakdown(
        overall_score=overall_score,
        code_quality_score=code_quality_score,
        process_score=process_score,
        devops_score=devops_score,
        ai_risk_score=ai_risk_score,
        previous_score=previous_score,
        percentage_change=percentage_change,
        status_trend=status_trend,
        category_health={
            "code_quality": code_quality_score,
            "process": process_score,
            "devops": devops_score,
        },
        key_drivers=key_drivers,
        top_strengths=strengths[:4],
        top_weaknesses=weaknesses[:4],
    )
