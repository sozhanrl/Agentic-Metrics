"""
Orchestrator — Wires all agents together into a single pipeline run.

Pipeline sequence
-----------------
1. Perceiver          — raw metrics + history → MetricSignals (with trend data)
2. AdaptiveWeighter   — context-aware category weights
3. ContextDetector    — domain classification & category weight overlay
4. Evaluator          — signals + weights → scored, filtered list
5. Negotiator         — cross-metric conflict resolution
6. Explainer          — per-recommendation title + explanation + dependency trail
7. ConfidenceEstimator— recommendation confidence score & evidence breakdown

The orchestrator is the only piece that knows about the full sequence.
Individual agents only know their own inputs/outputs, keeping them
independently testable and replaceable.
"""

from dataclasses import dataclass, field
from typing import Optional, Any

from app.agents.config import AgentConfig, default_config
from app.agents.perceiver import perceive_all, MetricSignal
from app.agents.adaptive_weighter import compute_adaptive_weights
from app.agents.context_detector import apply_domain_overlay, detect_domain
from app.agents.evaluator import evaluate_all
from app.agents.negotiator import negotiate
from app.agents.explainer import explain
from app.agents.confidence_estimator import estimate_confidence, DependencySupport, ConfidenceResult


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class EnrichedRecommendation:
    """
    Full pipeline output for one recommendation.
    This is what the recommendations router persists and returns to the client.
    """
    title:               str
    explanation:         str
    priority_score:      float
    related_metric_ids:  list[int]
    reasoning_trail:     list[str]       = field(default_factory=list)
    agent_trail:         list[dict]      = field(default_factory=list)
    adaptive_weights:    dict            = field(default_factory=dict)
    trend_slope:         float           = 0.0
    conflict_note:       Optional[str]   = None
    detected_domain:     Optional[str]   = None
    confidence_score:    float           = 0.0
    confidence_label:    str             = "low"
    confidence_evidence: list[str]       = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    metric_rows: list,
    history_map: dict | None = None,
    risk_profile=None,
    base_weights: dict | None = None,
    graph_edges: list | None = None,
    project: Any = None,
    weight_sample_sizes: dict | None = None,
    dependency_edges: dict | None = None,
    metric_learning_weights: dict | None = None,
    causal_edges: list | None = None,
    context_memories: list | None = None,
    cfg: AgentConfig | None = None,
) -> list[EnrichedRecommendation]:
    """
    Execute the full multi-agent pipeline for one project.

    Parameters
    ----------
    metric_rows             : list of (MetricValue, MetricDefinition) tuples
    history_map             : { metric_id: [MetricValue, …] } oldest-first per metric.
    risk_profile            : ProjectRiskProfile ORM object or None.
    base_weights            : Starting weights dict.
    graph_edges             : list of MetricDependencyGraph ORM objects (or None).
    project                 : Project ORM object or dict (or None).
    weight_sample_sizes     : dict of {category: sample_count} (or None).
    dependency_edges        : dict of {target_metric_key: edge_obj} (or None).
    metric_learning_weights : dict of per-metric Bayesian learning state (alpha, beta, sample_count).
    causal_edges            : list of active CausalEdge objects for self-evolving graph arbitration.
    context_memories        : list of ContextMemory objects for archetype predictiveness.
    cfg                     : AgentConfig. Defaults to module-level defaults if omitted.

    Returns
    -------
    list[EnrichedRecommendation] sorted highest priority_score first.
    """
    from app.agents.config import BASE_CATEGORY_WEIGHTS
    from app.agents.strategy_selector import select_strategy
    from app.agents.context_memory_engine import ContextMemoryEngine

    cfg                     = cfg or default_config()
    history_map             = history_map or {}
    base_weights            = base_weights or dict(BASE_CATEGORY_WEIGHTS)
    metric_learning_weights = metric_learning_weights or {}
    causal_edges            = causal_edges or []
    context_memories        = context_memories or []
    ctx_engine              = ContextMemoryEngine(cfg=cfg)

    # -----------------------------------------------------------------------
    # Step 1 — Perceiver
    # -----------------------------------------------------------------------
    signals: list[MetricSignal] = perceive_all(metric_rows, history_map, cfg)

    # Build a key-based lookup for the Explainer's dependency cross-references.
    signals_map: dict[str, MetricSignal] = {s.key: s for s in signals}

    # -----------------------------------------------------------------------
    # Step 1b — StrategySelector (Evidence-Adaptive Arbitration per metric)
    # -----------------------------------------------------------------------
    strategy_map: dict[str, dict] = {}
    for signal in signals:
        m_name = signal.key
        m_state = metric_learning_weights.get(m_name, {})
        alpha_val = float(m_state.get("alpha", 5.0))
        beta_val = float(m_state.get("beta", 5.0))
        samples = float(m_state.get("sample_count", 0.0))

        _, _, pred = ctx_engine.get_learned_priors(
            context_memories=context_memories,
            metric_name=m_name,
            fallback_alpha0=alpha_val,
            fallback_beta0=beta_val,
        )

        incoming = [
            e for e in causal_edges
            if (getattr(e, "target_metric", None) or (e.get("target_metric") if isinstance(e, dict) else None)) == m_name
        ]

        strat, reason, bayes_w, graph_w = select_strategy(
            metric_name=m_name,
            alpha=alpha_val,
            beta=beta_val,
            sample_count=samples,
            predictiveness=pred,
            incoming_causal_edges=incoming,
            cfg=cfg,
        )

        baseline_bayes_w, baseline_graph_w = 0.5, 0.5
        bayes_delta = round(bayes_w - baseline_bayes_w, 3)

        strategy_map[m_name] = {
            "strategy": strat.value,
            "reason": reason,
            "bayes_weight_factor": bayes_w,
            "graph_weight_factor": graph_w,
            "baseline_bayes_w": baseline_bayes_w,
            "bayes_delta_vs_baseline": bayes_delta,
            "predictiveness": pred,
            "sample_count": samples,
        }

        signal.agent_steps.append({
            "agent": "StrategySelector",
            "action": f"strategy={strat.value} (bayes_w={bayes_w:.2f}, graph_w={graph_w:.2f})",
            "detail": f"Arbitration for {m_name}: {reason}. [Baseline 50/50 blend delta={bayes_delta:+.2f}]",
        })

    # -----------------------------------------------------------------------
    # Step 2 — AdaptiveWeighter
    # -----------------------------------------------------------------------
    adaptive_weights, weighter_steps = compute_adaptive_weights(
        base_weights=base_weights,
        risk_profile=risk_profile,
        cfg=cfg,
    )

    # Apply per-metric weight multiplier scaled by StrategySelector factors
    for signal in signals:
        m_name = signal.key
        if m_name in metric_learning_weights and m_name in strategy_map:
            m_weight = float(metric_learning_weights[m_name].get("weight", 1.0))
            strat_info = strategy_map[m_name]
            bayes_factor = strat_info["bayes_weight_factor"]
            # Apply arbitrated Bayesian component vs raw weight
            effective_metric_mult = 1.0 + (m_weight - 1.0) * bayes_factor
            # Modulate adaptive category weight for this metric signal
            if signal.category in adaptive_weights:
                signal.weight_override = round(adaptive_weights[signal.category] * effective_metric_mult, 4)

    # -----------------------------------------------------------------------
    # Step 2b — ContextDetector (Domain Overlay)
    # -----------------------------------------------------------------------
    detected_domain = None
    if project is not None or risk_profile is not None:
        adaptive_weights, domain_step = apply_domain_overlay(
            weights=adaptive_weights,
            project=project,
            risk_profile=risk_profile,
        )
        weighter_steps.append(domain_step)
        detected_domain, _, _ = detect_domain(project, risk_profile)

    # -----------------------------------------------------------------------
    # Step 3 — Evaluator (filters below-threshold, scores rest)
    # -----------------------------------------------------------------------
    scored: list[tuple[MetricSignal, float]] = evaluate_all(signals, adaptive_weights, cfg)

    if not scored:
        return []  # Nothing significant to recommend

    # -----------------------------------------------------------------------
    # Step 4 — Negotiator (conflict resolution + graph-discount)
    # -----------------------------------------------------------------------
    negotiated: list[tuple[MetricSignal, float, str | None]] = negotiate(
        scored, cfg, graph_edges=graph_edges
    )

    # -----------------------------------------------------------------------
    # Step 5 — Explainer & ConfidenceEstimator
    # -----------------------------------------------------------------------
    results: list[EnrichedRecommendation] = []

    for signal, score, conflict_note in negotiated:
        title, explanation, trail, explainer_steps = explain(
            signal=signal,
            priority_score=score,
            weights=adaptive_weights,
            all_signals_map=signals_map,
            cfg=cfg,
        )

        # Lookup dependency support
        dep_support = None
        if dependency_edges and signal.key in dependency_edges:
            edge = dependency_edges[signal.key]
            edge_conf = getattr(edge, "confidence", None) or (edge.get("confidence") if isinstance(edge, dict) else "low")
            corr = getattr(edge, "correlation", 0.0) or (edge.get("correlation", 0.0) if isinstance(edge, dict) else 0.0)
            dep_support = DependencySupport(edge_confidence=str(edge_conf), correlation=float(corr))

        # Lookup weight sample size for signal's category or key
        sample_size = 0.0
        if weight_sample_sizes:
            sample_size = float(weight_sample_sizes.get(signal.category, weight_sample_sizes.get(signal.key, 0.0)))

        # Compute confidence
        conf_res: ConfidenceResult = estimate_confidence(
            signal=signal,
            weight_sample_size=sample_size,
            conflict_note=conflict_note,
            dependency_support=dep_support,
        )

        # Append Confidence summary line to reasoning trail
        trail.append(f"Confidence: {conf_res.score:.2f} ({conf_res.label.upper()}) — {', '.join(conf_res.evidence)}")

        conf_step = {
            "agent": "ConfidenceEstimator",
            "action": f"confidence={conf_res.score:.2f} ({conf_res.label})",
            "detail": f"Calculated confidence {conf_res.score:.2f} ({conf_res.label.upper()}). Factors: {'; '.join(conf_res.evidence)}.",
        }

        # Accumulate full agent provenance trail across all agents.
        all_agent_steps: list[dict] = (
            signal.agent_steps          # Perceiver steps (+ Evaluator + Negotiator)
            + weighter_steps            # AdaptiveWeighter + ContextDetector steps
            + explainer_steps
            + [conf_step]               # ConfidenceEstimator step
        )

        # Optionally append conflict note to reasoning trail
        if conflict_note:
            trail.append(conflict_note)

        results.append(EnrichedRecommendation(
            title=title,
            explanation=explanation,
            priority_score=score,
            related_metric_ids=[signal.metric_id],
            reasoning_trail=trail,
            agent_trail=all_agent_steps,
            adaptive_weights=dict(adaptive_weights),
            trend_slope=signal.trend_slope,
            conflict_note=conflict_note,
            detected_domain=detected_domain,
            confidence_score=conf_res.score,
            confidence_label=conf_res.label,
            confidence_evidence=conf_res.evidence,
        ))

    return results
