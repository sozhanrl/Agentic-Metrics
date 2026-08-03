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
    cfg: AgentConfig | None = None,
) -> list[EnrichedRecommendation]:
    """
    Execute the full multi-agent pipeline for one project.

    Parameters
    ----------
    metric_rows        : list of (MetricValue, MetricDefinition) tuples —
                         the latest value per metric (from crud.get_latest_metric_values)
    history_map        : { metric_id: [MetricValue, …] } oldest-first per metric.
                         Used by the Perceiver for trend detection.
    risk_profile       : ProjectRiskProfile ORM object or None.
                         Used by AdaptiveWeighter and ContextDetector.
    base_weights       : Starting weights dict (from crud.get_latest_weights or defaults).
                         If None, falls back to BASE_CATEGORY_WEIGHTS from config.
    graph_edges        : list of MetricDependencyGraph ORM objects (or None).
                         Pre-fetched by caller for Negotiator graph-discount.
    project            : Project ORM object or dict (or None). Used by ContextDetector.
    weight_sample_sizes: dict of {category: sample_count} (or None). Used by ConfidenceEstimator.
    dependency_edges   : dict of {target_metric_key: edge_obj} (or None). Used by ConfidenceEstimator.
    cfg                : AgentConfig. Defaults to module-level defaults if omitted.

    Returns
    -------
    list[EnrichedRecommendation] sorted highest priority_score first.
    """
    from app.agents.config import BASE_CATEGORY_WEIGHTS

    cfg          = cfg or default_config()
    history_map  = history_map or {}
    base_weights = base_weights or dict(BASE_CATEGORY_WEIGHTS)

    # -----------------------------------------------------------------------
    # Step 1 — Perceiver
    # -----------------------------------------------------------------------
    signals: list[MetricSignal] = perceive_all(metric_rows, history_map, cfg)

    # Build a key-based lookup for the Explainer's dependency cross-references.
    signals_map: dict[str, MetricSignal] = {s.key: s for s in signals}

    # -----------------------------------------------------------------------
    # Step 2 — AdaptiveWeighter
    # -----------------------------------------------------------------------
    adaptive_weights, weighter_steps = compute_adaptive_weights(
        base_weights=base_weights,
        risk_profile=risk_profile,
        cfg=cfg,
    )

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
