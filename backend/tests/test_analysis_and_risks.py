"""
Unit tests for Root Cause Analyzer, What-If Simulator, and Risk Predictor.
"""

from datetime import datetime, timezone, timedelta
from app.agents.root_cause_analyzer import analyze_root_cause
from app.agents.what_if_simulator import run_what_if_simulation
from app.agents.risk_predictor import predict_project_risks


class MockVal:
    def __init__(self, value, recorded_at):
        self.value = value
        self.recorded_at = recorded_at


class MockDef:
    def __init__(self, id, key, name, category, unit, higher_is_better):
        self.id = id
        self.key = key
        self.display_name = name
        self.category = category
        self.unit = unit
        self.higher_is_better = higher_is_better


def test_root_cause_analysis():
    now = datetime.now(timezone.utc)
    metrics_map = {
        "change_failure_rate": {"display_name": "Change Failure Rate", "category": "devops", "value": 28.0, "unit": "%", "higher_is_better": False},
        "test_coverage": {"display_name": "Test Coverage", "category": "code_quality", "value": 55.0, "unit": "%", "higher_is_better": True},
        "code_churn": {"display_name": "Code Churn", "category": "code_quality", "value": 24.0, "unit": "%", "higher_is_better": False},
    }

    causal_edges = [
        {"source_metric": "test_coverage", "target_metric": "change_failure_rate", "edge_strength": 0.85, "causal_confidence": 0.9, "effect_type": "direct", "is_active": True},
        {"source_metric": "code_churn", "target_metric": "test_coverage", "edge_strength": 0.78, "causal_confidence": 0.85, "effect_type": "indirect", "is_active": True},
    ]

    res = analyze_root_cause("change_failure_rate", metrics_map, causal_edges, [])
    assert res.target_metric == "change_failure_rate"
    assert len(res.causal_chain) >= 2
    assert res.root_metric_key in ("code_churn", "test_coverage")
    assert res.confidence_score > 0.5


def test_what_if_simulation_improves_health():
    now = datetime.now(timezone.utc)
    metric_rows = [
        (MockVal(55.0, now), MockDef(1, "test_coverage", "Test Coverage", "code_quality", "%", True)),
        (MockVal(6.0, now), MockDef(2, "cycle_time", "Cycle Time", "process", "days", False)),
    ]

    # Simulate improving test_coverage to 85% and cycle_time to 2.5 days
    res = run_what_if_simulation(
        metric_rows=metric_rows,
        simulated_values={"test_coverage": 85.0, "cycle_time": 2.5},
    )

    assert res.predicted_health > res.baseline_health
    assert res.health_delta > 0
    assert res.predicted_risk <= res.baseline_risk
    assert "test_coverage" in res.affected_metrics
    assert "cycle_time" in res.affected_metrics
    assert res.is_simulation is True


def test_risk_predictor_sufficient_and_insufficient():
    now = datetime.now(timezone.utc)
    
    # 1. Insufficient data (<4 points)
    sparse_metrics_map = {"change_failure_rate": {"id": 1, "value": 25.0}}
    sparse_history = {1: [MockVal(25.0, now)]}
    sparse_report = predict_project_risks(sparse_metrics_map, sparse_history)
    cfr_risk = next((r for r in sparse_report.risks if r.risk_category == "deployment_failure"), None)
    assert cfr_risk is not None
    assert cfr_risk.has_sufficient_data is False

    # 2. Sufficient data (5 points)
    dense_history = {
        1: [
            MockVal(15.0, now - timedelta(days=20)),
            MockVal(18.0, now - timedelta(days=15)),
            MockVal(22.0, now - timedelta(days=10)),
            MockVal(26.0, now - timedelta(days=5)),
            MockVal(30.0, now),
        ],
        2: [
            MockVal(85.0, now - timedelta(days=20)),
            MockVal(80.0, now - timedelta(days=15)),
            MockVal(70.0, now - timedelta(days=10)),
            MockVal(60.0, now - timedelta(days=5)),
            MockVal(55.0, now),
        ]
    }
    dense_metrics_map = {
        "change_failure_rate": {"id": 1, "value": 30.0},
        "test_coverage": {"id": 2, "value": 55.0}
    }
    dense_report = predict_project_risks(dense_metrics_map, dense_history)
    cfr_risk_dense = next((r for r in dense_report.risks if r.risk_category == "deployment_failure"), None)
    assert cfr_risk_dense is not None
    assert cfr_risk_dense.has_sufficient_data is True
    assert cfr_risk_dense.probability > 0.4
