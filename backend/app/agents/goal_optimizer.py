"""
Goal-Constrained Recommendation Optimizer — Phase 5.

Responsibility:
  Filters and reranks recommendations to satisfy user-defined goals and constraints
  (e.g., risk budget, cost limit, sprint duration limit).
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class OptimizationResult:
    recommendation: Any
    priority_score: float
    adjusted_score: float
    risk_impact: float
    cost_estimate: float
    time_estimate: float
    constraint_status: str


def satisfies_constraints(
    risk: float,
    cost: float,
    time: float,
    active_constraints: list,
) -> tuple[bool, str]:
    """
    Check if a recommendation's estimated risk/cost/time satisfies all active constraints.
    """
    for c in active_constraints:
        ctype = getattr(c, "constraint_type", "")
        cval  = float(getattr(c, "constraint_value", 0.0))

        if ctype == "risk_budget" and risk > cval:
            return False, f"Exceeds risk budget ({risk:.2f} > max {cval:.2f})"
        if ctype == "cost_limit" and cost > cval:
            return False, f"Exceeds cost limit ({cost:.1f} > max {cval:.1f} pts)"
        if ctype == "time_limit" and time > cval:
            return False, f"Exceeds time limit ({time:.1f} > max {cval:.1f} days)"

    return True, "Within all goal constraints"


def optimize_recommendations(
    scored_recommendations: list[tuple[Any, float, Any]],
    active_constraints: list,
    bayesian_states: dict[str, dict] | None = None,
) -> list[OptimizationResult]:
    """
    Filter and rerank recommendations based on risk budget, cost, and time constraints.
    """
    bayesian_states = bayesian_states or {}
    results: list[OptimizationResult] = []

    for signal, score, conflict_note in scored_recommendations:
        key = getattr(signal, "key", "")
        sev = float(getattr(signal, "severity", 1.0))
        b_state = bayesian_states.get(key, {})

        # Risk impact is derived from posterior variance (higher variance = higher risk)
        alpha = float(b_state.get("alpha", 5.0))
        beta  = float(b_state.get("beta", 5.0))
        total = alpha + beta
        variance = (alpha * beta) / ((total ** 2) * (total + 1)) if total > 0 else 0.1
        risk_impact = round(min(1.0, max(0.05, variance * 5.0)), 2)

        # Cost estimate: proportional to severity (e.g. 1.0 severity -> 3.0 story points)
        cost_estimate = round(max(1.0, sev * 3.0), 1)

        # Time estimate: proportional to severity (e.g. 1.0 severity -> 5.0 days)
        time_estimate = round(max(1.0, sev * 5.0), 1)

        ok, status_msg = satisfies_constraints(risk_impact, cost_estimate, time_estimate, active_constraints)

        if not ok:
            # Exceeded constraint -> skip or penalise
            adjusted_score = round(score * 0.5, 1)
        else:
            # Risk-adjusted benefit: boost items with low variance/risk
            adjusted_score = round(score * (1.0 - 0.2 * risk_impact), 1)

        results.append(OptimizationResult(
            recommendation=signal,
            priority_score=score,
            adjusted_score=adjusted_score,
            risk_impact=risk_impact,
            cost_estimate=cost_estimate,
            time_estimate=time_estimate,
            constraint_status=status_msg if ok else f"[CONSTRAINED] {status_msg}",
        ))

    results.sort(key=lambda r: r.adjusted_score, reverse=True)
    return results
