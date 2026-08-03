"""
Adaptive Learning Strategy Selector — Phase 4.

Responsibility:
  Meta-learner that dynamically selects the optimal learning strategy per metric:
    - pure_bayesian     : high data volume, low variance, high context predictiveness
    - graph_propagated  : strong causal edges, sparse direct feedback
    - hybrid            : medium evidence, blends Bayesian posterior and graph propagation
                          weighted by variance and predictiveness
"""

from enum import Enum
from typing import Any
from app.agents.config import AgentConfig, default_config


class Strategy(str, Enum):
    PURE_BAYESIAN = "pure_bayesian"
    GRAPH_PROPAGATED = "graph_propagated"
    HYBRID = "hybrid"


def select_strategy(
    metric_name: str,
    alpha: float,
    beta: float,
    sample_count: float,
    predictiveness: float,
    incoming_causal_edges: list,
    cfg: AgentConfig | None = None,
) -> tuple[Strategy, str, float, float]:
    """
    Selects learning strategy and computes (bayes_weight_factor, graph_weight_factor).

    Returns
    -------
    (strategy, reasoning_string, bayes_factor, graph_factor)
    """
    cfg = cfg or default_config()

    total = alpha + beta
    variance = (alpha * beta) / ((total ** 2) * (total + 1)) if total > 0 else 0.25
    has_sufficient_data = sample_count >= cfg.confidence_sample_target
    has_low_variance = variance < cfg.strategy_variance_threshold

    has_strong_graph = any(
        float(getattr(e, "edge_strength", 0.0) or 0.0) >= cfg.strategy_graph_confidence_threshold
        and float(getattr(e, "causal_confidence", 0.0) or 0.0) >= 0.4
        and getattr(e, "is_active", True)
        for e in incoming_causal_edges
    )

    if has_sufficient_data and has_low_variance and predictiveness >= 0.5:
        reason = f"High direct evidence ({sample_count:.1f} samples, var={variance:.4f}, predictiveness={predictiveness:.2f}) → Pure Bayesian strategy"
        return Strategy.PURE_BAYESIAN, reason, 1.0, 0.0

    if has_strong_graph and not has_sufficient_data:
        reason = f"Sparse direct data ({sample_count:.1f} samples) but strong causal graph support → Graph Propagated strategy"
        return Strategy.GRAPH_PROPAGATED, reason, 0.2, 0.8

    # Default: Hybrid strategy with certainty-weighted blending
    bayes_certainty = (1.0 - min(1.0, variance * 4.0)) * predictiveness
    graph_certainty = 0.5
    if incoming_causal_edges:
        avg_str = sum(float(getattr(e, "edge_strength", 0.5)) for e in incoming_causal_edges) / len(incoming_causal_edges)
        graph_certainty = avg_str

    tot_certainty = bayes_certainty + graph_certainty
    w_bayes = round(bayes_certainty / tot_certainty, 3) if tot_certainty > 0 else 0.5
    w_graph = round(1.0 - w_bayes, 3)

    reason = f"Hybrid strategy: {w_bayes:.0%} Bayesian posterior / {w_graph:.0%} Causal graph (bayes_certainty={bayes_certainty:.2f}, graph_certainty={graph_certainty:.2f})"
    return Strategy.HYBRID, reason, w_bayes, w_graph
