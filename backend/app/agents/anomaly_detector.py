"""
AI Anomaly Detection Agent — AI Software Engineering Intelligence Platform.

Automatically detects unusual, sharp, or out-of-band metric shifts.
Uses rolling statistical analysis (Z-score + rate-of-change + threshold boundary violations)
against empirical history.

Grounds root causes using the causal dependencies and known domain heuristics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Optional, Any

from app.agents.config import AgentConfig, default_config, DEFAULT_TARGETS, METRIC_DEPENDENCIES


@dataclass
class AnomalySignal:
    metric_key: str
    metric_name: str
    category: str
    current_value: float
    unit: str
    expected_min: float
    expected_max: float
    deviation_pct: float
    severity: str  # 'critical' | 'warning' | 'info'
    z_score: float
    detected_at: datetime
    possible_cause: str
    recommended_action: str
    historical_count: int


POSSIBLE_CAUSES = {
    "test_coverage": "Large un-tested merge batch or deletion of legacy test suites without replacement.",
    "cycle_time": "Blocked PR reviews, complex cross-service dependencies, or CI test queue congestion.",
    "change_failure_rate": "Insufficient pre-merge validation, config drift between staging and prod, or flaky integration tests.",
    "deployment_frequency": "Pipeline build freeze, failing deployment steps, or large batching of changes.",
    "mttr": "Lack of automated rollback mechanisms, delayed alert routing, or insufficient observability traces.",
    "code_churn": "Rapid mid-sprint requirement pivots, incomplete specs, or thrashing during refactoring.",
    "defect_density": "Rushed sprint deliveries, skipped QA cycles, or complex unmaintainable code paths.",
    "cyclomatic_complexity": "Overly nested conditional branches, large God-classes, or missing domain abstraction.",
    "sprint_velocity": "Unplanned interrupt work, mis-estimated story complexities, or cross-team dependencies.",
    "lead_time": "Upstream backlog refinement delays, long wait times in approval stages, or QA handoff friction.",
}

RECOMMENDED_ACTIONS = {
    "test_coverage": "Enforce minimum coverage check gates on PR CI pipeline and add regression tests for recent modules.",
    "cycle_time": "Institute WIP limits per engineer and introduce 4-hour PR review SLAs for the team.",
    "change_failure_rate": "Implement automated canary rollouts and mandate synthetic smoke test validation pre-promotion.",
    "deployment_frequency": "Decompose large feature releases into decoupled micro-PRs behind feature toggles.",
    "mttr": "Automate 1-click canary rollback runbooks and refine PagerDuty routing policies.",
    "code_churn": "Freeze architectural designs prior to implementation and review scope changes with product managers.",
    "defect_density": "Initiate automated static analysis scanning and allocate 20% of sprint capacity to tech debt remediation.",
    "cyclomatic_complexity": "Refactor monolithic functions into composable single-responsibility handlers.",
    "sprint_velocity": "Re-calibrate sprint capacity during planning and ring-fence developers from ad-hoc operational interrupts.",
    "lead_time": "Streamline stage-gate approvals and adopt continuous delivery deployment patterns.",
}


def detect_metric_anomalies(
    latest_metrics: list,
    history_map: dict[int, list],
    cfg: Optional[AgentConfig] = None,
) -> list[AnomalySignal]:
    """
    Examine metric values and their time-series history to discover anomalies.
    
    Parameters
    ----------
    latest_metrics: list of (MetricValue, MetricDefinition) tuples or dicts
    history_map: { metric_id: [MetricValue, ...] } sorted oldest to newest
    """
    cfg = cfg or default_config()
    anomalies: list[AnomalySignal] = []
    now = datetime.now(timezone.utc)

    for item in latest_metrics:
        if isinstance(item, tuple):
            val_obj, defn = item
            metric_id = defn.id
            key = defn.key
            name = defn.display_name
            cat = defn.category
            unit = defn.unit or ""
            hib = defn.higher_is_better
            cur_val = float(val_obj.value)
        else:
            metric_id = item.get("metric_id", item.get("id"))
            key = item.get("metric_key", item.get("key"))
            name = item.get("display_name", key)
            cat = item.get("category", "general")
            unit = item.get("unit", "")
            hib = item.get("higher_is_better", True)
            cur_val = float(item.get("value", 0.0))

        history = history_map.get(metric_id, [])
        all_vals = [float(h.value) for h in history] if history else [cur_val]

        if len(all_vals) >= 3:
            # Statistical calculation
            mean = sum(all_vals) / len(all_vals)
            variance = sum((x - mean) ** 2 for x in all_vals) / max(1, len(all_vals) - 1)
            std_dev = math.sqrt(variance)
            z_score = abs(cur_val - mean) / max(1e-4, std_dev) if std_dev > 0 else 0.0

            exp_min = round(max(0.0, mean - 1.96 * std_dev), 2)
            exp_max = round(mean + 1.96 * std_dev, 2)
        else:
            # Fallback to target definition bounds if history is sparse
            target_info = cfg.default_targets.get(key, {"target": cur_val, "tolerance": max(1.0, cur_val * 0.2)})
            target = float(target_info["target"])
            tol = float(target_info["tolerance"])
            mean = target
            exp_min = round(max(0.0, target - tol), 2)
            exp_max = round(target + tol, 2)
            z_score = abs(cur_val - target) / max(1e-4, tol)

        # Rate of change from previous sample
        prev_val = all_vals[-2] if len(all_vals) >= 2 else mean
        step_delta = cur_val - prev_val
        step_pct_change = (step_delta / max(1e-4, abs(prev_val))) * 100.0 if prev_val != 0 else 0.0

        # Check if anomalous
        is_bad_direction = (cur_val < mean) if hib else (cur_val > mean)
        is_step_bad = (step_delta < 0) if hib else (step_delta > 0)

        # Conditions for anomaly:
        # 1. Z-score >= 2.0 and in bad direction
        # 2. Sudden jump >= 35% in bad direction
        # 3. Severe target violation (> 2.5x tolerance)
        is_anomaly = False
        severity = "info"

        if is_bad_direction and z_score >= 2.3:
            is_anomaly = True
            severity = "critical" if z_score >= 3.0 else "warning"
        elif is_step_bad and abs(step_pct_change) >= 40.0:
            is_anomaly = True
            severity = "warning" if abs(step_pct_change) < 70.0 else "critical"
        elif (cur_val < exp_min if hib else cur_val > exp_max) and is_bad_direction:
            is_anomaly = True
            severity = "warning"

        if is_anomaly:
            dev_pct = round(((cur_val - mean) / max(1e-4, abs(mean))) * 100.0, 1)

            # Look up upstream root causes from causal dependencies
            upstream_deps = METRIC_DEPENDENCIES.get(key, [])
            cause = POSSIBLE_CAUSES.get(key, "Unexpected variance observed in metric pipeline.")
            if upstream_deps:
                cause = f"{cause} (Upstream contributing factors: {', '.join(upstream_deps)})."

            action = RECOMMENDED_ACTIONS.get(key, "Investigate recent commit history and CI logs for root cause.")

            anomalies.append(AnomalySignal(
                metric_key=key,
                metric_name=name,
                category=cat,
                current_value=cur_val,
                unit=unit,
                expected_min=exp_min,
                expected_max=exp_max,
                deviation_pct=dev_pct,
                severity=severity,
                z_score=round(z_score, 2),
                detected_at=now,
                possible_cause=cause,
                recommended_action=action,
                historical_count=len(all_vals),
            ))

    # Sort critical first, then warning, then highest deviation
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    anomalies.sort(key=lambda a: (severity_rank.get(a.severity, 3), -abs(a.deviation_pct)))
    return anomalies
