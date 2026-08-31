"""
What-If Simulation Engine — AI Software Engineering Intelligence Platform.

In-memory sandbox for simulating hypothetical metric interventions:
- User modifies test_coverage, cycle_time, deployment_frequency, etc.
- In-memory re-execution of Perceiver, HealthScorer, and Priority Engine.
- Calculates predicted health score, predicted risk score, re-ranked recommendation queue,
  affected metrics, and expected net improvement.
- STRICT CONTRACT: Pure in-memory computation. NEVER modifies database state.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

from app.agents.config import AgentConfig, default_config, DEFAULT_TARGETS, BASE_CATEGORY_WEIGHTS
from app.agents.perceiver import perceive, MetricSignal
from app.agents.health_scorer import compute_health_score, HealthScoreBreakdown


@dataclass
class SimulatedRecommendationDiff:
    metric_key: str
    title: str
    baseline_priority: float
    simulated_priority: float
    priority_delta: float
    rank_before: int
    rank_after: int
    status: str  # improved | unchanged | degraded | resolved


@dataclass
class WhatIfSimulationResult:
    baseline_health: float
    predicted_health: float
    health_delta: float
    health_percentage_gain: float
    baseline_risk: float
    predicted_risk: float
    risk_delta: float
    affected_metrics: list[str]
    recommendation_diffs: list[SimulatedRecommendationDiff]
    projected_category_health: dict
    simulation_notes: list[str]
    is_simulation: bool = True
    simulated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def run_what_if_simulation(
    metric_rows: list,
    simulated_values: dict[str, float],
    risk_profile: Optional[Any] = None,
    base_weights: Optional[dict] = None,
    cfg: Optional[AgentConfig] = None,
) -> WhatIfSimulationResult:
    """
    Run what-if scenario with simulated metric values.
    
    Parameters
    ----------
    metric_rows: list of (MetricValue, MetricDefinition) tuples representing real project data
    simulated_values: dict of { metric_key: new_value }
    """
    cfg = cfg or default_config()
    weights = base_weights or dict(BASE_CATEGORY_WEIGHTS)

    # 1. Baseline signals & health
    baseline_signals: list[MetricSignal] = []
    baseline_val_map = {}

    for val_row, defn in metric_rows:
        sig = perceive(val_row, defn, history=None, cfg=cfg)
        baseline_signals.append(sig)
        baseline_val_map[defn.key] = float(val_row.value)

    baseline_health_breakdown = compute_health_score(
        signals=baseline_signals,
        adaptive_weights=weights,
        cfg=cfg,
    )

    # 2. Build simulated signals (in-memory modified copies)
    simulated_signals: list[MetricSignal] = []
    affected_keys = []

    class MockVal:
        def __init__(self, value, recorded_at):
            self.value = value
            self.recorded_at = recorded_at

    for val_row, defn in metric_rows:
        key = defn.key
        if key in simulated_values:
            sim_val = float(simulated_values[key])
            sim_val_row = MockVal(sim_val, val_row.recorded_at)
            sig = perceive(sim_val_row, defn, history=None, cfg=cfg)
            affected_keys.append(key)
        else:
            sig = perceive(val_row, defn, history=None, cfg=cfg)
        simulated_signals.append(sig)

    simulated_health_breakdown = compute_health_score(
        signals=simulated_signals,
        adaptive_weights=weights,
        cfg=cfg,
    )

    # 3. Priority scoring comparison for recommendations
    def _score_sig(s: MetricSignal) -> float:
        w = weights.get(s.category, 1.0)
        return round(min(s.severity * w * 40.0, 100.0), 1)

    baseline_ranked = sorted(
        [(s, _score_sig(s)) for s in baseline_signals if s.severity > 0.3],
        key=lambda x: x[1],
        reverse=True
    )
    baseline_ranks = {item[0].key: (idx + 1, item[1]) for idx, item in enumerate(baseline_ranked)}

    simulated_ranked = sorted(
        [(s, _score_sig(s)) for s in simulated_signals if s.severity > 0.3],
        key=lambda x: x[1],
        reverse=True
    )
    simulated_ranks = {item[0].key: (idx + 1, item[1]) for idx, item in enumerate(simulated_ranked)}

    diffs: list[SimulatedRecommendationDiff] = []
    all_recs_keys = set(baseline_ranks.keys()) | set(simulated_ranks.keys())

    for key in all_recs_keys:
        b_rank, b_score = baseline_ranks.get(key, (len(baseline_ranked) + 1, 0.0))
        s_rank, s_score = simulated_ranks.get(key, (len(simulated_ranked) + 1, 0.0))
        p_delta = round(s_score - b_score, 1)

        status = "unchanged"
        if s_score < b_score:
            status = "resolved" if s_score == 0 else "improved"
        elif s_score > b_score:
            status = "degraded"

        defn_name = key.replace("_", " ").title()
        diffs.append(SimulatedRecommendationDiff(
            metric_key=key,
            title=f"Priority adjustment for {defn_name}",
            baseline_priority=b_score,
            simulated_priority=s_score,
            priority_delta=p_delta,
            rank_before=b_rank,
            rank_after=s_rank,
            status=status,
        ))

    diffs.sort(key=lambda d: d.priority_delta)

    # 4. Deltas
    base_h = baseline_health_breakdown.overall_score
    pred_h = simulated_health_breakdown.overall_score
    h_delta = round(pred_h - base_h, 2)
    h_pct_gain = round((h_delta / max(1e-4, base_h)) * 100.0, 1) if base_h > 0 else 0.0

    base_r = baseline_health_breakdown.ai_risk_score
    pred_r = simulated_health_breakdown.ai_risk_score
    r_delta = round(pred_r - base_r, 2)

    notes = [
        f"Simulating changes across {len(affected_keys)} metric(s): {', '.join(affected_keys)}.",
        f"Health score projects from {base_h:.1f} to {pred_h:.1f} ({h_delta:+.1f} pts, {h_pct_gain:+.1f}%).",
        f"System risk index shifts from {base_r:.1f} to {pred_r:.1f} ({r_delta:+.1f} pts).",
    ]

    return WhatIfSimulationResult(
        baseline_health=base_h,
        predicted_health=pred_h,
        health_delta=h_delta,
        health_percentage_gain=h_pct_gain,
        baseline_risk=base_r,
        predicted_risk=pred_r,
        risk_delta=r_delta,
        affected_metrics=affected_keys,
        recommendation_diffs=diffs,
        projected_category_health=simulated_health_breakdown.category_health,
        simulation_notes=notes,
    )
