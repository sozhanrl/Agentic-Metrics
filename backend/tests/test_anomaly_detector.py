"""
Unit tests for Anomaly Detector Agent.
"""

from datetime import datetime, timezone, timedelta
from app.agents.anomaly_detector import detect_metric_anomalies


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


def test_detect_sudden_drop_anomaly():
    now = datetime.now(timezone.utc)
    defn = MockDef(1, "test_coverage", "Test Coverage", "code_quality", "%", True)

    # History: steadily ~80%, then sudden plunge to 40%
    history = [
        MockVal(80.0, now - timedelta(days=20)),
        MockVal(81.0, now - timedelta(days=15)),
        MockVal(79.0, now - timedelta(days=10)),
        MockVal(80.0, now - timedelta(days=5)),
        MockVal(40.0, now),
    ]

    latest = [(history[-1], defn)]
    history_map = {1: history}

    anomalies = detect_metric_anomalies(latest, history_map)
    assert len(anomalies) == 1
    assert anomalies[0].metric_key == "test_coverage"
    assert anomalies[0].severity in ("critical", "warning")
    assert anomalies[0].possible_cause != ""
    assert anomalies[0].recommended_action != ""


def test_no_anomaly_when_stable():
    now = datetime.now(timezone.utc)
    defn = MockDef(2, "cycle_time", "Cycle Time", "process", "days", False)

    history = [
        MockVal(3.0, now - timedelta(days=15)),
        MockVal(3.1, now - timedelta(days=10)),
        MockVal(2.9, now - timedelta(days=5)),
        MockVal(3.0, now),
    ]

    latest = [(history[-1], defn)]
    history_map = {2: history}

    anomalies = detect_metric_anomalies(latest, history_map)
    assert len(anomalies) == 0
