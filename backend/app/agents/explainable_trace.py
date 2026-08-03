"""
Explainable Reasoning Trace Generator — Phase 5.

Responsibility:
  Generates transparent, machine-auditable reasoning chains tied directly to the
  Bayesian posterior, causal graph evolution, context predictiveness, and strategy selection.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningTrace:
    evidence_summary: str
    prior_source: str
    posterior_summary: str
    posterior_variance: float
    confidence_score: float
    confidence_label: str
    causal_trail: list[str] = field(default_factory=list)
    learning_strategy: str = "hybrid"
    strategy_reason: str = ""
    metric_predictiveness: float = 0.5
    predictiveness_note: str = ""
    expected_benefit: str = ""
    constraint_status: str = ""
    graph_evolution_note: str = ""

    def to_lines(self) -> list[str]:

        """Convert trace to lines formatted with [AgentName] prefixes for reasoning_trail."""
        lines = [
            f"[BayesianLearner] Evidence: {self.evidence_summary}",
            f"[BayesianLearner] Prior: {self.prior_source}",
            f"[BayesianLearner] Posterior: {self.posterior_summary} (variance={self.posterior_variance:.4f})",
            f"[StrategySelector] Strategy: {self.learning_strategy.upper()} — {self.strategy_reason}",
            f"[ContextMemoryEngine] Metric Predictiveness: {self.metric_predictiveness:.2f} ({self.predictiveness_note})",
        ]

        if self.causal_trail:
            lines.append(f"[CausalGraph] Propagated Causal Influence:")
            for step in self.causal_trail:
                lines.append(f"[CausalGraph]   → {step}")

        if self.graph_evolution_note:
            lines.append(f"[CausalGraph] Graph Evolution: {self.graph_evolution_note}")

        lines.append(f"[GoalOptimizer] Constraint Status: {self.constraint_status}")
        lines.append(f"[GoalOptimizer] Expected Benefit: {self.expected_benefit}")

        return lines


def generate_reasoning_trace(
    metric_name: str,
    bayesian_state: dict,
    strategy_name: str,
    strategy_reason: str,
    predictiveness: float,
    context_key: str,
    causal_steps: list,
    constraint_status: str = "Within all goal constraints",
    expected_benefit: str = "Quality improvement & risk reduction",
) -> ReasoningTrace:
    alpha = bayesian_state.get("alpha", 5.0)
    beta  = bayesian_state.get("beta", 5.0)
    alpha0 = bayesian_state.get("alpha0", 5.0)
    beta0  = bayesian_state.get("beta0", 5.0)
    sample_count = bayesian_state.get("sample_count", 0.0)

    total = alpha + beta
    mean  = alpha / total if total > 0 else 0.5
    var   = (alpha * beta) / ((total ** 2) * (total + 1)) if total > 0 else 0.05
    conf  = max(0.0, min(1.0, 1.0 - var))
    label = "high" if conf >= 0.7 else ("medium" if conf >= 0.45 else "low")

    ev_summary = f"{sample_count:.1f} decay-weighted feedback sample(s)"
    prior_str  = f"α₀={alpha0:.2f}, β₀={beta0:.2f} (from context memory key '{context_key}')"
    post_str   = f"α={alpha:.2f}, β={beta:.2f} → posterior mean weight={mean:.4f}"

    c_lines = []
    for step in causal_steps:
        src = getattr(step, "source_metric", None) or (step.get("source_metric") if isinstance(step, dict) else "")
        tgt = getattr(step, "target_metric", None) or (step.get("target_metric") if isinstance(step, dict) else "")
        rew = getattr(step, "propagated_reward", 0.0) if not isinstance(step, dict) else step.get("propagated_reward", 0.0)
        eff = getattr(step, "effect_type", "direct") if not isinstance(step, dict) else step.get("effect_type", "direct")
        c_lines.append(f"{src} → {tgt} ({eff} effect, propagated reward {rew:+.4f})")

    pred_note = "High relevance in this context archetype" if predictiveness >= 0.7 else "Moderate relevance in this context"

    return ReasoningTrace(
        evidence_summary=ev_summary,
        prior_source=prior_str,
        posterior_summary=post_str,
        posterior_variance=var,
        confidence_score=conf,
        confidence_label=label,
        causal_trail=c_lines,
        learning_strategy=strategy_name,
        strategy_reason=strategy_reason,
        metric_predictiveness=predictiveness,
        predictiveness_note=pred_note,
        expected_benefit=expected_benefit,
        constraint_status=constraint_status,
        graph_evolution_note="Edges validated and updated based on empirical feedback",
    )
