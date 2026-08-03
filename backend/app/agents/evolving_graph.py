"""
Self-Evolving Causal Knowledge Graph Engine — Phase 2.

Responsibility:
  Discovers, refines, strengthens, weakens, and retires causal edges based on
  empirical feedback and measured outcomes. Distinguishes direct vs indirect
  effects, evaluates competing hypotheses, and performs multi-hop causal propagation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Optional

from app.agents.config import AgentConfig, default_config


@dataclass
class CausalPropagationStep:
    source_metric: str
    target_metric: str
    propagated_reward: float
    edge_strength: float
    causal_confidence: float
    effect_type: str
    evidence_type: str


@dataclass
class EvolutionReport:
    strengthened: list[dict] = field(default_factory=list)
    weakened: list[dict]     = field(default_factory=list)
    created: list[dict]      = field(default_factory=list)
    retired: list[dict]      = field(default_factory=list)


class EvolvingCausalGraph:
    """
    Manages the lifecycle of causal dependency edges per project.
    """

    def __init__(self, cfg: AgentConfig | None = None):
        self.cfg = cfg or default_config()

    def classify_effect_type(self, source: str, target: str, active_edges: list) -> str:
        """
        Determines whether a causal path source -> target is direct or indirect
        based on whether an active multi-step path exists.
        """
        sources_of_target = [e.source_metric for e in active_edges if e.target_metric == target and e.is_active]
        for mid in sources_of_target:
            if mid != source:
                # If mid is fed by source, then source -> mid -> target is indirect
                mid_sources = [e.source_metric for e in active_edges if e.target_metric == mid and e.is_active]
                if source in mid_sources:
                    return "indirect"
        return "direct"

    def evaluate_competing_hypotheses(
        self,
        target_metric: str,
        outcome_delta: float,
        candidate_edges: list,
    ) -> list[tuple[str, Any, float]]:
        """
        When target_metric improves/worsens, evaluate all incoming edges as competing hypotheses.
        Returns list of (action, edge, score).
        """
        if not candidate_edges:
            return []

        # Competing hypotheses scoring: higher correlation/strength gets stronger credit
        scores = []
        for edge in candidate_edges:
            confidence_bonus = float(getattr(edge, "causal_confidence", 0.5) or 0.5)
            strength = float(getattr(edge, "edge_strength", 0.5) or 0.5)
            score = strength * (0.5 + 0.5 * confidence_bonus)
            scores.append((edge, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        best_score = scores[0][1] if scores else 1.0

        results = []
        for edge, score in scores:
            edge.competing_hypotheses = len(candidate_edges)
            if score >= best_score * 0.8 and outcome_delta > 0:
                edge.confirmations = (getattr(edge, "confirmations", 0) or 0) + 1
                edge.edge_strength = min(1.0, float(edge.edge_strength) + self.cfg.edge_strengthen_rate * (score / max(1e-6, best_score)))
                results.append(("strengthened", edge, score))
            elif outcome_delta <= 0 or score < best_score * 0.5:
                edge.refutations = (getattr(edge, "refutations", 0) or 0) + 1
                edge.edge_strength = max(0.0, float(edge.edge_strength) - self.cfg.edge_weaken_rate)
                results.append(("weakened", edge, score))

        return results

    def propagate_learning(
        self,
        source_metric: str,
        reward: float,
        active_edges: list,
        visited: set[str] | None = None,
    ) -> list[CausalPropagationStep]:
        """
        Attenuated multi-hop causal propagation starting from source_metric.
        """
        visited = visited or {source_metric}
        trail: list[CausalPropagationStep] = []

        outgoing = [e for e in active_edges if getattr(e, "source_metric", None) == source_metric and getattr(e, "is_active", True)]

        for edge in outgoing:
            target = edge.target_metric
            if target in visited:
                continue

            strength = float(getattr(edge, "edge_strength", 0.5))
            conf = float(getattr(edge, "causal_confidence", 0.5))
            effect_type = getattr(edge, "effect_type", "direct")
            evidence_type = getattr(edge, "evidence_type", "correlation")

            attenuation = self.cfg.graph_propagation_decay
            if effect_type == "indirect":
                attenuation *= self.cfg.indirect_effect_decay

            propagated = reward * strength * (0.5 + 0.5 * conf) * attenuation

            if abs(propagated) < 0.001:
                continue

            step = CausalPropagationStep(
                source_metric=source_metric,
                target_metric=target,
                propagated_reward=round(propagated, 4),
                edge_strength=round(strength, 4),
                causal_confidence=round(conf, 4),
                effect_type=effect_type,
                evidence_type=evidence_type,
            )
            trail.append(step)

            visited.add(target)
            deeper = self.propagate_learning(target, propagated, active_edges, visited)
            trail.extend(deeper)

        return trail

    def validate_and_retire_edges(self, active_edges: list) -> list[Any]:
        """
        Check active edges; promote evidence level or retire edges if consistently failing.
        """
        retired = []
        for edge in active_edges:
            confirmations = getattr(edge, "confirmations", 0) or 0
            refutations   = getattr(edge, "refutations", 0) or 0
            total = confirmations + refutations
            strength = float(getattr(edge, "edge_strength", 0.5))

            if total >= self.cfg.causal_min_observations:
                conf_rate = confirmations / total
                edge.causal_confidence = round(min(1.0, 0.6 * conf_rate + 0.4 * (strength)), 4)
                if conf_rate > 0.7:
                    edge.evidence_type = "intervention"

            if strength < self.cfg.edge_removal_threshold:
                edge.is_active = False
                retired.append(edge)

        return retired
