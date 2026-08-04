"""
Unit tests for strategy_selector.select_strategy() proving the patent claim behaviors:

  1. Low direct samples + high-confidence edge  -> graph_propagated
  2. High direct samples + low variance         -> pure_bayesian (regardless of graph)
  3. Edge refutation & retirement               -> strategy changes away from graph_propagated
  4. Mixed evidence                             -> hybrid strategy scaling continuously
"""

import pytest
from app.agents.strategy_selector import select_strategy, Strategy
from app.agents.config import AgentConfig
from app.agents.evolving_graph import EvolvingCausalGraph


def make_cfg(**overrides) -> AgentConfig:
    cfg = AgentConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class DummyEdge:
    def __init__(self, source_metric, target_metric, edge_strength, causal_confidence, is_active=True):
        self.source_metric = source_metric
        self.target_metric = target_metric
        self.edge_strength = edge_strength
        self.causal_confidence = causal_confidence
        self.is_active = is_active


class TestStrategySelectorRules:
    """Tests verifying the decision logic of the evidence-adaptive Strategy Selector."""

    def test_low_samples_strong_edge_selects_graph_propagated(self):
        """
        Given low direct-feedback sample count (< 30) + high-confidence incoming causal edge,
        strategy_selector MUST select graph_propagated.
        """
        cfg = make_cfg(confidence_sample_target=30, strategy_graph_confidence_threshold=0.6)
        strong_edge = DummyEdge("test_coverage", "defect_density", edge_strength=0.8, causal_confidence=0.7)

        strat, reason, bayes_w, graph_w = select_strategy(
            metric_name="defect_density",
            alpha=5.0,
            beta=5.0,
            sample_count=2.0,  # low sample count
            predictiveness=0.5,
            incoming_causal_edges=[strong_edge],
            cfg=cfg,
        )

        assert strat == Strategy.GRAPH_PROPAGATED
        assert graph_w > bayes_w
        assert "strong causal graph support" in reason

    def test_high_samples_selects_pure_bayesian_regardless_of_graph(self):
        """
        Given high direct-feedback sample count (>= 30) and low variance,
        strategy_selector MUST select pure_bayesian regardless of causal edge strength.
        """
        cfg = make_cfg(confidence_sample_target=30, strategy_variance_threshold=0.08)
        strong_edge = DummyEdge("test_coverage", "defect_density", edge_strength=0.9, causal_confidence=0.9)

        # High sample count with accumulated alpha=25, beta=5 (low variance, high confidence)
        total = 30
        var = (25 * 5) / ((total ** 2) * (total + 1))  # 125 / (900 * 31) = 0.0044 < 0.08

        strat, reason, bayes_w, graph_w = select_strategy(
            metric_name="defect_density",
            alpha=25.0,
            beta=5.0,
            sample_count=35.0,  # high direct evidence
            predictiveness=0.8,
            incoming_causal_edges=[strong_edge],
            cfg=cfg,
        )

        assert strat == Strategy.PURE_BAYESIAN
        assert bayes_w == 1.0
        assert graph_w == 0.0
        assert "Pure Bayesian strategy" in reason

    def test_refuted_edge_retirement_changes_subsequent_strategy(self):
        """
        Given a causal edge that gets refuted repeatedly and retired (is_active=False),
        confirm strategy_selector's subsequent decision changes and no longer offers graph_propagated.
        """
        cfg = make_cfg(confidence_sample_target=30, strategy_graph_confidence_threshold=0.6, edge_removal_threshold=0.15)
        edge = DummyEdge("test_coverage", "defect_density", edge_strength=0.7, causal_confidence=0.6, is_active=True)

        # Phase 1: Edge is active and strong -> graph_propagated selected
        strat1, _, _, _ = select_strategy(
            metric_name="defect_density",
            alpha=5.0,
            beta=5.0,
            sample_count=1.0,
            predictiveness=0.5,
            incoming_causal_edges=[edge],
            cfg=cfg,
        )
        assert strat1 == Strategy.GRAPH_PROPAGATED

        # Phase 2: Graph self-corrects after repeated refutations -> edge strength drops and gets retired
        graph = EvolvingCausalGraph(cfg=cfg)
        edge.confirmations = 0
        edge.refutations = 10
        edge.edge_strength = 0.05  # below removal threshold (0.15)
        retired = graph.validate_and_retire_edges([edge])

        assert len(retired) == 1
        assert edge.is_active is False

        # Phase 3: Subsequent strategy selection query -> retired edge is inactive, strategy changes to HYBRID
        strat2, reason2, bayes_w2, graph_w2 = select_strategy(
            metric_name="defect_density",
            alpha=5.0,
            beta=5.0,
            sample_count=1.0,
            predictiveness=0.5,
            incoming_causal_edges=[edge],  # inactive edge passed
            cfg=cfg,
        )

        assert strat2 != Strategy.GRAPH_PROPAGATED
        assert strat2 == Strategy.HYBRID
        assert "Hybrid strategy" in reason2

    def test_mixed_evidence_hybrid_scales_continuously(self):
        """
        Given mixed/medium evidence, confirm hybrid weighting scales continuously with variance/predictiveness,
        not as a discrete step function.
        """
        cfg = make_cfg(confidence_sample_target=30)
        edge = DummyEdge("test_coverage", "defect_density", edge_strength=0.5, causal_confidence=0.3)

        # Measure bayes factor as variance decreases (or certainty increases)
        # Low certainty -> bayes_w is lower
        strat1, _, bayes_w1, graph_w1 = select_strategy(
            metric_name="defect_density",
            alpha=5.0,
            beta=5.0,
            sample_count=10.0,
            predictiveness=0.3,
            incoming_causal_edges=[edge],
            cfg=cfg,
        )

        # Higher predictiveness & certainty -> bayes_w increases continuously
        strat2, _, bayes_w2, graph_w2 = select_strategy(
            metric_name="defect_density",
            alpha=12.0,
            beta=6.0,
            sample_count=18.0,
            predictiveness=0.6,
            incoming_causal_edges=[edge],
            cfg=cfg,
        )

        assert strat1 == Strategy.HYBRID
        assert strat2 == Strategy.HYBRID
        assert bayes_w2 > bayes_w1
        assert abs((bayes_w1 + graph_w1) - 1.0) < 1e-3
        assert abs((bayes_w2 + graph_w2) - 1.0) < 1e-3


if __name__ == "__main__":
    pytest.main([__file__])
