"""
Root Cause Analysis Engine — AI Software Engineering Intelligence Platform.

Generates deep causal diagnostic explanations when a metric becomes problematic.
Walks the active causal graph and empirical dependencies to identify root metrics,
contributing factors, confidence scores, evidence traces, and system impact.

Example:
Deployment Failure (Symptom)
  ↓ [direct: correlation r=0.74, conf=0.82]
Change Failure Rate ↑
  ↓ [indirect: intervention evidence, conf=0.89]
Test Coverage ↓
  ↓ [root cause: high code churn r=0.68]
Code Churn ↑
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from app.agents.config import AgentConfig, default_config, METRIC_DEPENDENCIES, DEFAULT_TARGETS


@dataclass
class CausalNode:
    metric_key: str
    display_name: str
    category: str
    current_value: float
    unit: str
    deviation_pct: float
    is_root_cause: bool
    relation_to_parent: Optional[str] = None  # direct | indirect
    edge_strength: float = 1.0
    confidence: float = 0.8
    evidence_type: str = "correlation"


@dataclass
class RootCauseExplanation:
    target_metric: str
    target_display_name: str
    severity: str
    summary: str
    causal_chain: list[CausalNode] = field(default_factory=list)
    contributing_metrics: list[str] = field(default_factory=list)
    root_metric_key: Optional[str] = None
    root_metric_name: Optional[str] = None
    confidence_score: float = 0.0
    evidence_summary: str = ""
    system_impact: str = ""
    recommended_intervention: str = ""


def analyze_root_cause(
    target_metric_key: str,
    latest_metrics_map: dict[str, Any],
    causal_edges: list,
    dependency_edges: list,
    cfg: Optional[AgentConfig] = None,
) -> RootCauseExplanation:
    """
    Perform backward causal graph traversal from target_metric_key to uncover root causes.
    """
    cfg = cfg or default_config()
    target_data = latest_metrics_map.get(target_metric_key, {})
    target_name = target_data.get("display_name", target_metric_key.replace("_", " ").title())
    target_val = float(target_data.get("value", 0.0))
    target_unit = target_data.get("unit", "")
    target_cat = target_data.get("category", "general")

    # Trace upstream ancestors
    visited = set()
    chain: list[CausalNode] = []
    contributing = []

    def get_edge_prop(e, prop, default):
        if isinstance(e, dict):
            return e.get(prop, default)
        return getattr(e, prop, default)

    current_key = target_metric_key

    while current_key and current_key not in visited:
        visited.add(current_key)
        m_info = latest_metrics_map.get(current_key, {})
        m_val = float(m_info.get("value", 0.0))
        m_name = m_info.get("display_name", current_key.replace("_", " ").title())
        m_unit = m_info.get("unit", "")
        m_cat = m_info.get("category", "general")

        # Find best incoming causal edge or fallback to METRIC_DEPENDENCIES
        incoming = [
            e for e in causal_edges
            if get_edge_prop(e, "target_metric", None) == current_key and bool(get_edge_prop(e, "is_active", True))
        ]

        upstream_key = None
        rel_type = "direct"
        strength = 0.75
        conf = 0.8
        ev_type = "correlation"

        if incoming:
            # Pick strongest incoming edge
            incoming.sort(key=lambda e: float(get_edge_prop(e, "edge_strength", 0.5)), reverse=True)
            best_edge = incoming[0]
            upstream_key = get_edge_prop(best_edge, "source_metric", None)
            rel_type = get_edge_prop(best_edge, "effect_type", "direct")
            strength = float(get_edge_prop(best_edge, "edge_strength", 0.5))
            conf = float(get_edge_prop(best_edge, "causal_confidence", 0.6))
            ev_type = get_edge_prop(best_edge, "evidence_type", "correlation")
        elif current_key in METRIC_DEPENDENCIES:
            deps = METRIC_DEPENDENCIES[current_key]
            # Pick first dependency not yet visited
            for d in deps:
                if d not in visited:
                    upstream_key = d
                    rel_type = "direct"
                    strength = 0.65
                    conf = 0.7
                    ev_type = "domain_prior"
                    break

        is_root = upstream_key is None or upstream_key in visited

        # Calculate deviation
        target_info = cfg.default_targets.get(current_key, {"target": m_val, "tolerance": 1.0})
        t_val = float(target_info["target"])
        hib = m_info.get("higher_is_better", True)
        dev = ((t_val - m_val) if hib else (m_val - t_val)) / max(1e-4, t_val) * 100.0

        node = CausalNode(
            metric_key=current_key,
            display_name=m_name,
            category=m_cat,
            current_value=m_val,
            unit=m_unit,
            deviation_pct=round(dev, 1),
            is_root_cause=is_root,
            relation_to_parent=rel_type if chain else None,
            edge_strength=round(strength, 2),
            confidence=round(conf, 2),
            evidence_type=ev_type,
        )
        chain.append(node)

        if current_key != target_metric_key:
            contributing.append(m_name)

        if is_root:
            break
        current_key = upstream_key

    root_node = chain[-1] if chain else None
    root_key = root_node.metric_key if root_node else target_metric_key
    root_name = root_node.display_name if root_node else target_name

    avg_conf = sum(n.confidence for n in chain) / len(chain) if chain else 0.8
    chain_str = " → ".join(n.display_name for n in chain)

    summary = (
        f"Degradation in {target_name} ({target_val}{target_unit}) is traced to "
        f"root cause in '{root_name}' ({chain_str})."
    )

    evidence_summary = (
        f"Causal evidence supported by {len(chain)} link(s) across empirical correlation, "
        f"temporal precedence, and evolving graph confirmations."
    )

    system_impact = (
        f"Downstream propagation impacts {len(contributing) + 1} engineering indicators, "
        f"accumulating process friction and delivery risk."
    )

    intervention = (
        f"Prioritize remediation on {root_name} to arrest upstream defect generation and "
        f"cascade positive recovery across {target_name}."
    )

    return RootCauseExplanation(
        target_metric=target_metric_key,
        target_display_name=target_name,
        severity="critical" if abs(chain[0].deviation_pct) > 30 else "warning",
        summary=summary,
        causal_chain=chain,
        contributing_metrics=contributing,
        root_metric_key=root_key,
        root_metric_name=root_name,
        confidence_score=round(avg_conf, 2),
        evidence_summary=evidence_summary,
        system_impact=system_impact,
        recommended_intervention=intervention,
    )
