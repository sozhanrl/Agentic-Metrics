"""
Orchestrator — Wires all agents together into a single pipeline run.

Pipeline sequence
-----------------
1. Perceiver      — raw metrics + history → MetricSignals (with trend data)
2. AdaptiveWeighter → context-aware category weights
3. Evaluator      — signals + weights → scored, filtered list
4. Negotiator     — cross-metric conflict resolution
5. Explainer      — per-recommendation title + explanation + dependency trail

The orchestrator is the only piece that knows about the full sequence.
Individual agents only know their own inputs/outputs, keeping them
independently testable and replaceable.

The ai_engine.py narration layer is applied after the Explainer, just before
persisting to DB — it rewrites the explanation in a more advisory tone while
keeping all factual claims from the trail unchanged.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.agents.config import AgentConfig, default_config
from app.agents.perceiver import perceive_all, MetricSignal
from app.agents.adaptive_weighter import compute_adaptive_weights
from app.agents.evaluator import evaluate_all
from app.agents.negotiator import negotiate
from app.agents.explainer import explain


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class EnrichedRecommendation:
    """
    Full pipeline output for one recommendation.
    This is what the recommendations router persists and returns to the client.
    """
    title:            str
    explanation:      str
    priority_score:   float
    related_metric_ids: list[int]
    reasoning_trail:  list[str]       = field(default_factory=list)
    agent_trail:      list[dict]      = field(default_factory=list)
    adaptive_weights: dict            = field(default_factory=dict)
    trend_slope:      float           = 0.0
    conflict_note:    Optional[str]   = None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    metric_rows: list,
    history_map: dict | None = None,
    risk_profile=None,
    base_weights: dict | None = None,
    graph_edges: list | None = None,
    cfg: AgentConfig | None = None,
) -> list[EnrichedRecommendation]:
    """
    Execute the full multi-agent pipeline for one project.

    Parameters
    ----------
    metric_rows   : list of (MetricValue, MetricDefinition) tuples —
                    the latest value per metric (from crud.get_latest_metric_values)
    history_map   : { metric_id: [MetricValue, …] } oldest-first per metric.
                    Used by the Perceiver for trend detection.
    risk_profile  : ProjectRiskProfile ORM object or None.
                    Used by AdaptiveWeighter.
    base_weights  : Starting weights dict (from crud.get_latest_weights or defaults).
                    If None, falls back to BASE_CATEGORY_WEIGHTS from config.
    graph_edges   : list of MetricDependencyGraph ORM objects (or None).
                    Pre-fetched by the caller (router) so the orchestrator stays
                    DB-free and independently testable.  Passed to the Negotiator
                    to apply graph-discount on empirically discovered causal edges.
    cfg           : AgentConfig. Defaults to module-level defaults if omitted.

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
    # Step 5 — Explainer (title + explanation + trail per recommendation)
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

        # Accumulate the full agent provenance trail across all agents.
        all_agent_steps: list[dict] = (
            signal.agent_steps          # Perceiver steps (+ Evaluator + Negotiator appended in-place)
            + weighter_steps            # AdaptiveWeighter steps (shared across all recs)
            + explainer_steps
        )

        # Optionally append the conflict note to the trail.
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
        ))

    return results
