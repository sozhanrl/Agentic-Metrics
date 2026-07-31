"""
Explainer Agent — Idea #4: Dependency-Aware Reasoning Trails.

Responsibility:
  Turn a scored MetricSignal into a human-readable title, explanation, and a
  structured reasoning trail that:

  1. Carries [AgentName] prefixes on every line so readers can trace which
     agent contributed which insight.
  2. Includes dependency context: if the flagged metric has known upstream
     causes (from METRIC_DEPENDENCIES in config.py), the trail mentions those
     contributing factors and indicates whether they are also off-target.
  3. Reflects the adaptive weights and trend data produced earlier in the
     pipeline, so the explanation faithfully represents what actually drove
     the score.
"""

from app.agents.perceiver import MetricSignal
from app.agents.config import AgentConfig, default_config


def explain(
    signal: MetricSignal,
    priority_score: float,
    weights: dict[str, float],
    all_signals_map: dict[str, "MetricSignal"] | None = None,
    cfg: AgentConfig | None = None,
) -> tuple[str, str, list[str], list[dict]]:
    """
    Produce the full explanation for one recommendation.

    Parameters
    ----------
    signal           : MetricSignal (Perceiver output, may have been annotated
                       by Negotiator)
    priority_score   : Final priority score (post-Negotiator)
    weights          : Adaptive weights used in this run
    all_signals_map  : { metric_key: MetricSignal } for ALL metrics in this run,
                       used for dependency cross-references.
    cfg              : AgentConfig

    Returns
    -------
    (title, explanation, reasoning_trail, explainer_agent_steps)
    """
    cfg             = cfg or default_config()
    all_signals_map = all_signals_map or {}
    key             = signal.key
    unit            = signal.unit or ""
    direction       = "below target" if signal.higher_is_better else "above target"
    weight          = weights.get(signal.category, 1.0)
    target_info     = cfg.default_targets.get(key, {})
    target_val      = target_info.get("target", "n/a")

    # -----------------------------------------------------------------------
    # Title
    # -----------------------------------------------------------------------
    title = (
        f"{signal.display_name} is {abs(signal.deviation_pct):.0f}% {direction}"
        + (" ↗ trending worse" if signal.trend_direction == "worsening" else "")
    )

    # -----------------------------------------------------------------------
    # Reasoning trail (tagged lines)
    # -----------------------------------------------------------------------
    trail: list[str] = []

    # — Perceiver block
    trail.append(
        f"[Perceiver] Observed {signal.display_name}: "
        f"{signal.value}{unit} (recorded {signal.recorded_at.date()})"
    )
    trail.append(
        f"[Perceiver] Target: {target_val}{unit}  |  "
        f"Deviation: {signal.deviation_pct:+.1f}%  |  "
        f"Base severity: {signal.severity:.2f}"
    )

    if signal.trend_direction == "worsening":
        trail.append(
            f"[Perceiver] ⚠ Trend worsening — slope={signal.trend_slope:+.3f}/period; "
            f"severity amplified by {signal.trend_amplification:.1%} "
            f"→ adjusted severity={signal.severity:.2f}"
        )
    elif signal.trend_direction == "improving":
        trail.append(
            f"[Perceiver] ✓ Trend improving (slope={signal.trend_slope:+.3f}/period); "
            f"no severity amplification."
        )
    else:
        trail.append(
            f"[Perceiver] Trend flat (slope={signal.trend_slope:+.3f}/period)."
        )

    # — AdaptiveWeighter block
    trail.append(
        f"[AdaptiveWeighter] Category '{signal.category}' weight applied: "
        f"{weight:.4f} (base was {cfg.base_weights.get(signal.category, 1.0):.1f})"
    )

    # — Evaluator block
    trail.append(
        f"[Evaluator] Priority score: {priority_score} / 100"
    )

    # — Dependency block (Explainer's unique contribution)
    dependencies = cfg.metric_dependencies.get(key, [])
    if dependencies:
        trail.append(
            f"[Explainer] '{signal.display_name}' is downstream of: "
            f"{', '.join(dependencies)}"
        )
        for dep_key in dependencies:
            dep_sig = all_signals_map.get(dep_key)
            if dep_sig is None:
                trail.append(
                    f"[Explainer]   → '{dep_key}': no data available in this run."
                )
            elif dep_sig.severity > cfg.severity_threshold:
                trail.append(
                    f"[Explainer]   → '{dep_sig.display_name}' is ALSO off-target "
                    f"(severity={dep_sig.severity:.2f}); likely a contributing cause."
                )
            else:
                trail.append(
                    f"[Explainer]   → '{dep_sig.display_name}' is within target "
                    f"(severity={dep_sig.severity:.2f}); not a root cause here."
                )

    # -----------------------------------------------------------------------
    # Explanation (prose summary for the recommendation card)
    # -----------------------------------------------------------------------
    explanation = (
        f"{signal.display_name} is currently {signal.value}{unit}, "
        f"which is {abs(signal.deviation_pct):.0f}% {direction} "
        f"(target: {target_val}{unit}). "
        f"This falls in the '{signal.category.replace('_', ' ')}' category, "
        f"weighted {weight:.2f}× in overall project health "
        f"after adaptive context adjustment."
    )
    if signal.trend_direction == "worsening":
        explanation += (
            f" The metric has been trending in the wrong direction "
            f"(slope {signal.trend_slope:+.3f}/period), increasing urgency."
        )
    if dependencies:
        off_target_deps = [
            d for d in dependencies
            if all_signals_map.get(d) and all_signals_map[d].severity > cfg.severity_threshold
        ]
        if off_target_deps:
            dep_names = ", ".join(
                all_signals_map[d].display_name for d in off_target_deps
            )
            explanation += (
                f" Contributing upstream factors also off-target: {dep_names}."
            )

    # Explainer provenance step
    explainer_steps = [{
        "agent":  "Explainer",
        "action": "explanation-generated",
        "detail": (
            f"Trail has {len(trail)} lines; "
            f"{len(dependencies)} dependencies checked; "
            f"title='{title}'"
        ),
    }]

    return title, explanation, trail, explainer_steps
