"""
Unit tests for Health Scorer Agent.
"""

from datetime import datetime, timezone
from app.agents.health_scorer import compute_health_score, _calculate_metric_health
from app.agents.perceiver import MetricSignal
from app.agents.config import default_config


def test_metric_health_calculation():
    targets = {"test_coverage": {"target": 80, "tolerance": 15}, "cycle_time": {"target": 3, "tolerance": 2}}

    # Higher is better: 85% >= 80% -> 100
    h1 = _calculate_metric_health(85.0, "test_coverage", True, targets)
    assert h1 == 100.0

    # Higher is better: 65% is 15 below target -> 50
    h2 = _calculate_metric_health(65.0, "test_coverage", True, targets)
    assert h2 == 50.0

    # Lower is better: 2.0 <= 3.0 -> 100
    h3 = _calculate_metric_health(2.0, "cycle_time", False, targets)
    assert h3 == 100.0

    # Lower is better: 5.0 is 2.0 above target -> 50
    h4 = _calculate_metric_health(5.0, "cycle_time", False, targets)
    assert h4 == 50.0


def test_compute_health_score_all_healthy():
    now = datetime.now(timezone.utc)
    signals = [
        MetricSignal(1, "test_coverage", "Test Coverage", "code_quality", "%", True, 85.0, now),
        MetricSignal(2, "code_churn", "Code Churn", "code_quality", "%", False, 10.0, now),
        MetricSignal(3, "sprint_velocity", "Sprint Velocity", "process", "pts", True, 32.0, now),
        MetricSignal(4, "deployment_frequency", "Deployment Frequency", "devops", "/wk", True, 3.5, now),
    ]

    res = compute_health_score(signals)
    assert res.overall_score == 100.0
    assert res.code_quality_score == 100.0
    assert res.process_score == 100.0
    assert res.devops_score == 100.0
    assert res.ai_risk_score <= 10.0
    assert len(res.top_strengths) > 0


def test_compute_health_score_with_degraded_metrics():
    now = datetime.now(timezone.utc)
    signals = [
        MetricSignal(1, "test_coverage", "Test Coverage", "code_quality", "%", True, 50.0, now, severity=1.2),
        MetricSignal(2, "cycle_time", "Cycle Time", "process", "days", False, 7.0, now, severity=1.5, trend_direction="worsening"),
    ]

    res = compute_health_score(signals)
    assert res.overall_score < 70.0
    assert res.ai_risk_score > 20.0
    assert len(res.top_weaknesses) > 0
