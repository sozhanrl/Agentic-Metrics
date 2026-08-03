"""
Context Memory Engine — Phase 3.

Responsibility:
  Learns Bayesian priors (alpha0, beta0) AND metric predictiveness per project context
  (domain, risk tolerance, team size, tech debt index) from historical project outcomes.
"""

from dataclasses import dataclass
from typing import Any
from app.agents.config import AgentConfig, default_config
from app.agents.context_detector import detect_domain


def build_context_key(project: Any = None, risk_profile: Any = None) -> str:
    """
    Construct a deterministic context string representing project archetype.
    Example: 'banking:medium:large:high'
    """
    domain, _, _ = detect_domain(project, risk_profile)

    risk_tol = "medium"
    team_size = 10
    tech_debt = 0.5

    if risk_profile:
        risk_tol = getattr(risk_profile, "risk_tolerance", None) or (risk_profile.get("risk_tolerance") if isinstance(risk_profile, dict) else "medium") or "medium"
        team_size = getattr(risk_profile, "team_size", None) or (risk_profile.get("team_size") if isinstance(risk_profile, dict) else 10) or 10
        tech_debt = float(getattr(risk_profile, "tech_debt_index", None) or (risk_profile.get("tech_debt_index") if isinstance(risk_profile, dict) else 0.5) or 0.5)

    size_bucket = "small" if int(team_size) <= 5 else "large"
    debt_bucket = "high" if float(tech_debt) > 0.65 else "low"

    return f"{domain}:{risk_tol}:{size_bucket}:{debt_bucket}"


class ContextMemoryEngine:
    """
    Stores and retrieves learned priors and predictiveness per context key.
    """

    def __init__(self, cfg: AgentConfig | None = None):
        self.cfg = cfg or default_config()

    def get_learned_priors(
        self,
        context_memories: list,
        metric_name: str,
        fallback_alpha0: float,
        fallback_beta0: float,
    ) -> tuple[float, float, float]:
        """
        Returns (alpha0, beta0, predictiveness) for metric in this context.
        Falls back to default priors if context memory has insufficient historical project samples.
        """
        match = next((m for m in context_memories if getattr(m, "metric_name", None) == metric_name), None)

        if match and getattr(match, "project_count", 0) >= self.cfg.context_memory_min_projects:
            alpha0 = float(getattr(match, "learned_alpha0", fallback_alpha0))
            beta0  = float(getattr(match, "learned_beta0", fallback_beta0))
            pred   = float(getattr(match, "predictiveness", 0.5))
            return alpha0, beta0, pred

        return fallback_alpha0, fallback_beta0, 0.5

    def update_predictiveness(
        self,
        existing_predictiveness: float,
        weight_delta: float,
        outcome_delta: float,
    ) -> float:
        """
        Adjust predictiveness score [0..1] based on whether weight delta led to positive outcome.
        """
        aligns = (weight_delta > 0 and outcome_delta > 0) or (weight_delta < 0 and outcome_delta <= 0)
        nudge = 0.05 if aligns else -0.05
        new_pred = max(0.0, min(1.0, existing_predictiveness + nudge))
        return round(new_pred * self.cfg.predictiveness_decay, 4)
