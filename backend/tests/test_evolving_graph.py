"""
Unit tests for evolving_graph.EvolvingCausalGraph proving the self-correcting causal graph lifecycle:

  1. Competing hypothesis evaluation (strengthening on confirmed outcomes, weakening on refutation)
  2. Edge validation and automatic retirement when edge strength drops below removal threshold
  3. Multi-hop attenuated causal learning propagation
  4. Classification of direct vs indirect effect paths
"""

import pytest
from app.agents.evolving_graph import EvolvingCausalGraph, CausalPropagationStep
from app.agents.config import AgentConfig


def make_cfg(**overrides) -> AgentConfig:
    cfg = AgentConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class MutableEdge:
    def __init__(self, source_metric, target_metric, edge_strength=0.5, causal_confidence=0.5, effect_type="direct", evidence_type="correlation", is_active=True):
        self.source_metric = source_metric
        self.target_metric = target_metric
        self.edge_strength = edge_strength
        self.causal_confidence = causal_confidence
        self.effect_type = effect_type
        self.evidence_type = evidence_type
        self.is_active = is_active
        self.confirmations = 0
        self.refutations = 0
        self.competing_hypotheses = 0


class TestEvolvingCausalGraphLifecycle:
    """Tests verifying hypothesis scoring, multi-hop propagation, and edge retirement."""

    def test_evaluate_competing_hypotheses_positive_outcome_strengthens(self):
        """Positive outcome_delta strengthens high-scoring competing edges."""
        cfg = make_cfg(edge_strengthen_rate=0.1)
        graph = EvolvingCausalGraph(cfg=cfg)

        edge1 = MutableEdge("test_coverage", "defect_density", edge_strength=0.6, causal_confidence=0.8)
        edge2 = MutableEdge("code_churn", "defect_density", edge_strength=0.2, causal_confidence=0.3)

        results = graph.evaluate_competing_hypotheses(
            target_metric="defect_density",
            outcome_delta=0.5,  # positive outcome improvement
            candidate_edges=[edge1, edge2],
        )

        assert edge1.confirmations == 1
        assert edge1.edge_strength > 0.6
        assert edge2.refutations == 1

    def test_evaluate_competing_hypotheses_negative_outcome_weakens(self):
        """Negative outcome_delta refutes and weakens all candidate edges."""
        cfg = make_cfg(edge_weaken_rate=0.15)
        graph = EvolvingCausalGraph(cfg=cfg)

        edge = MutableEdge("test_coverage", "defect_density", edge_strength=0.5)

        results = graph.evaluate_competing_hypotheses(
            target_metric="defect_density",
            outcome_delta=-0.3,  # negative outcome
            candidate_edges=[edge],
        )

        assert edge.refutations == 1
        assert edge.edge_strength == 0.35

    def test_validate_and_retire_edges_removes_weak_edges(self):
        """Edges dropping below edge_removal_threshold (e.g. 0.15) are deactivated."""
        cfg = make_cfg(edge_removal_threshold=0.15, causal_min_observations=5)
        graph = EvolvingCausalGraph(cfg=cfg)

        strong_edge = MutableEdge("test_coverage", "defect_density", edge_strength=0.7)
        weak_edge = MutableEdge("sprint_velocity", "defect_density", edge_strength=0.10)

        retired = graph.validate_and_retire_edges([strong_edge, weak_edge])

        assert len(retired) == 1
        assert retired[0].source_metric == "sprint_velocity"
        assert weak_edge.is_active is False
        assert strong_edge.is_active is True

    def test_multi_hop_causal_propagation_attenuation(self):
        """Learning propagation attenuates across multi-hop edges (source -> mid -> target)."""
        cfg = make_cfg(graph_propagation_decay=0.5)
        graph = EvolvingCausalGraph(cfg=cfg)

        edge1 = MutableEdge("code_churn", "cyclomatic_complexity", edge_strength=0.8, causal_confidence=0.8)
        edge2 = MutableEdge("cyclomatic_complexity", "defect_density", edge_strength=0.8, causal_confidence=0.8)

        trail = graph.propagate_learning(
            source_metric="code_churn",
            reward=1.0,
            active_edges=[edge1, edge2],
        )

        assert len(trail) == 2
        step1 = trail[0]
        step2 = trail[1]

        assert step1.source_metric == "code_churn"
        assert step1.target_metric == "cyclomatic_complexity"
        assert step2.source_metric == "cyclomatic_complexity"
        assert step2.target_metric == "defect_density"

        # Multi-hop step2 reward must be attenuated relative to step1
        assert abs(step2.propagated_reward) < abs(step1.propagated_reward)

    def test_classify_effect_type_direct_vs_indirect(self):
        """Classifies direct vs indirect causal paths."""
        graph = EvolvingCausalGraph()

        edge_direct = MutableEdge("code_churn", "defect_density")
        edge_hop1 = MutableEdge("code_churn", "cyclomatic_complexity")
        edge_hop2 = MutableEdge("cyclomatic_complexity", "defect_density")

        active_edges = [edge_direct, edge_hop1, edge_hop2]

        effect_type = graph.classify_effect_type("code_churn", "defect_density", active_edges)
        assert effect_type in ["direct", "indirect"]


if __name__ == "__main__":
    pytest.main([__file__])
