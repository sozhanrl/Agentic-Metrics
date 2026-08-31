"""
Unit tests for Action Planner Agent.
"""

from app.agents.action_planner import build_action_plan


def test_build_action_plan_critical_coverage():
    plan = build_action_plan(
        metric_key="test_coverage",
        title="Test Coverage is 25% below target",
        priority_score=68.0,
        confidence_score=0.85,
        deviation_pct=-25.0,
    )

    assert plan.problem == "Test Coverage is 25% below target"
    assert plan.priority == "Critical"
    assert "PR coverage gates" in plan.recommended_action
    assert plan.confidence_pct == 85
    assert "story points" in plan.estimated_effort
    assert plan.why_it_matters != ""
    assert plan.success_criteria != ""


def test_build_action_plan_with_upstream_deps():
    plan = build_action_plan(
        metric_key="defect_density",
        title="Defect Density is 40% above target",
        priority_score=52.0,
        confidence_score=0.72,
        deviation_pct=40.0,
        upstream_deps=["test_coverage", "code_churn"],
    )

    assert "test_coverage" in plan.root_cause
    assert "code_churn" in plan.root_cause
    assert plan.priority == "High"
