"""
Evaluator Agent

Responsibility:
  Convert a MetricSignal's severity into a final priority score using the
  adaptive weights produced by AdaptiveWeighter for this project run.

This is a thin, pure function — no I/O, no side effects — making it trivial
to unit-test and easy to swap for a learned model without touching the
orchestrator.
"""

from app.agents.perceiver import MetricSignal
from app.agents.config import AgentConfig, default_config


def evaluate(
    signal: MetricSignal,
    weights: dict[str, float],
    cfg: AgentConfig | None = None,
) -> tuple[float, dict]:
    """
    Score a single MetricSignal.

    Parameters
    ----------
    signal  : MetricSignal from the Perceiver
    weights : Adaptive category weights from AdaptiveWeighter
    cfg     : AgentConfig

    Returns
    -------
    (priority_score, agent_step)
      priority_score : float in [0, 100]
      agent_step     : provenance dict for the reasoning trail
    """
    cfg    = cfg or default_config()
    weight = weights.get(signal.category, 1.0)
    raw    = signal.severity * weight * cfg.score_scale
    score  = round(min(raw, 100.0), 1)

    step = {
        "agent":  "Evaluator",
        "action": "score-computed",
        "detail": (
            f"severity={signal.severity:.2f} × weight[{signal.category}]={weight:.4f} "
            f"× scale={cfg.score_scale} = {raw:.1f} → capped at {score}"
        ),
    }

    return score, step


def evaluate_all(
    signals: list[MetricSignal],
    weights: dict[str, float],
    cfg: AgentConfig | None = None,
) -> list[tuple[MetricSignal, float]]:
    """
    Score all signals, returning only those above the severity threshold.

    Returns
    -------
    List of (MetricSignal, priority_score) tuples, sorted highest score first.
    """
    cfg     = cfg or default_config()
    results = []

    for signal in signals:
        if signal.severity <= cfg.severity_threshold:
            signal.agent_steps.append({
                "agent":  "Evaluator",
                "action": "below-threshold",
                "detail": (
                    f"severity={signal.severity:.2f} ≤ threshold={cfg.severity_threshold}; "
                    f"recommendation suppressed."
                ),
            })
            continue

        score, step = evaluate(signal, weights, cfg)
        signal.agent_steps.append(step)
        results.append((signal, score))

    results.sort(key=lambda t: t[1], reverse=True)
    return results
