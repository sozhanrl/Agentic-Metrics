"""
Self-Learning Module — Feedback-Driven Bayesian Weight Updates (v2).

Upgrades over v1
----------------
1.  Per-metric granularity  (not just per-category)
    test_coverage and defect_density are both 'code_quality', but a team may
    find coverage advice useless and defect-density advice invaluable.  Feedback
    is now bucketed by metric_name first; category acts as a fallback prior when
    a specific metric has fewer than min_feedback_samples.

2.  Outcome signal blended as stronger signal
    outcome_delta (measured improvement after acting on a recommendation) is
    weighted more heavily than subjective was_helpful (opinion).  When outcome
    data is absent the blend falls back to subjective-only.

3.  Confidence-scaled learning rate
    effective_rate = SELF_LEARNING_RATE * min(1, decay_weighted_total / CONFIDENCE_SAMPLE_TARGET)
    A metric with 3 samples barely moves; one with 300 can shift decisively.

4.  Recency decay
    Feedback aggregation applies exponential decay by feedback age before it
    arrives here — so old ratings count less than recent ones.  This module
    receives the already-decayed stats (decay is applied in crud.py).

5.  Full learning-state tracking  (weight, confidence, sample_count, trend)
    Each update log entry carries:
      weight        — the new multiplicative adjustment
      confidence    — 0–1, how much evidence supports this weight
      sample_count  — decay-weighted total feedback seen
      trend         — 'increasing' | 'decreasing' | 'stable'

Algorithm (unchanged core, extended)
--------------------------------------
For each metric (or category fallback) with sufficient decay-weighted samples:

  helpfulness_rate = helpful_w / total_w                    (decay-weighted)
  outcome_signal   = tanh(outcome_delta_sum_w / total_w)    (-1 … +1)

  If outcome data is present (|outcome_delta_sum_w| > epsilon):
    combined = 0.35 * helpfulness_rate + 0.65 * (outcome_signal + 1) / 2
  Else:
    combined = helpfulness_rate   (subjective only)

  confidence_factor = min(1.0, total_w / confidence_sample_target)
  effective_rate    = self_learning_rate * confidence_factor

  nudge    = (combined - 0.5) * 2.0 * effective_rate
  new_weight = clamp(old_weight + old_weight * nudge, weight_min, weight_max)

  trend = 'increasing' if new_w > old_w
          'decreasing' if new_w < old_w
          'stable'     otherwise
"""

import math
from app.agents.config import AgentConfig, default_config


# Blend ratios when outcome data is available vs. absent.
OUTCOME_BLEND_WEIGHT    = 0.65   # portion assigned to measured outcome_delta
SUBJECTIVE_BLEND_WEIGHT = 0.35   # portion assigned to was_helpful opinion
OUTCOME_EPSILON         = 1e-6   # threshold to consider outcome data "present"


def compute_weight_updates(
    feedback_summary: dict[str, dict],
    current_weights: dict[str, float],
    metric_feedback_summary: dict[str, dict] | None = None,
    current_metric_weights: dict[str, dict] | None = None,
    cfg: AgentConfig | None = None,
) -> tuple[dict[str, float], list[dict], dict[str, dict]]:
    """
    Compute updated category weights AND per-metric weight adjustments.

    Parameters
    ----------
    feedback_summary : { category: { "total_w": float, "helpful_w": float,
                                      "outcome_delta_sum_w": float } }
                       as returned by crud.get_feedback_summary (with decay applied).
    current_weights  : Current category weights (starting point).
    metric_feedback_summary : { metric_name: { "total_w": float, "helpful_w": float,
                                               "outcome_delta_sum_w": float,
                                               "category": str } }
                       as returned by crud.get_feedback_summary_by_metric.
                       If None, only category-level learning is applied.
    current_metric_weights : { metric_name: { "weight": float, "confidence": float,
                                              "sample_count": float, "trend": str } }
                       Current per-metric learning state from metric_weights table.
    cfg              : AgentConfig

    Returns
    -------
    (new_category_weights, update_log, new_metric_weights)
      new_category_weights : dict[str, float]   — updated category weights
      update_log           : list[dict]          — one entry per updated/skipped item
      new_metric_weights   : dict[str, dict]     — updated per-metric learning state
    """
    cfg                    = cfg or default_config()
    new_weights            = dict(current_weights)
    current_metric_weights = current_metric_weights or {}
    update_log: list[dict] = []
    new_metric_weights: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Pass 1 — Category-level updates (fallback prior)
    # ------------------------------------------------------------------
    for category, stats in feedback_summary.items():
        total_w   = stats.get("total_w", stats.get("total", 0))
        helpful_w = stats.get("helpful_w", stats.get("helpful", 0))
        delta_w   = stats.get("outcome_delta_sum_w", stats.get("outcome_delta_sum", 0.0))

        if total_w < cfg.min_feedback_samples:
            update_log.append({
                "level":     "category",
                "category":  category,
                "action":    "skipped",
                "reason":    (
                    f"Only {total_w:.1f} decay-weighted feedback sample(s); "
                    f"minimum is {cfg.min_feedback_samples}."
                ),
                "old_weight": current_weights.get(category),
                "new_weight": current_weights.get(category),
            })
            continue

        old_w, new_w, entry = _compute_single_update(
            key=category,
            level="category",
            total_w=float(total_w),
            helpful_w=float(helpful_w),
            delta_w=float(delta_w),
            old_weight=current_weights.get(category, 1.0),
            prev_weight=current_weights.get(category, 1.0),
            cfg=cfg,
        )
        new_weights[category] = new_w
        update_log.append(entry)

    # ------------------------------------------------------------------
    # Pass 2 — Per-metric updates (primary signal when data is available)
    # ------------------------------------------------------------------
    if metric_feedback_summary:
        for metric_name, stats in metric_feedback_summary.items():
            total_w   = float(stats.get("total_w", stats.get("total", 0)))
            helpful_w = float(stats.get("helpful_w", stats.get("helpful", 0)))
            delta_w   = float(stats.get("outcome_delta_sum_w", stats.get("outcome_delta_sum", 0.0)))

            existing  = current_metric_weights.get(metric_name, {})
            old_weight = float(existing.get("weight", 1.0))

            if total_w < cfg.min_feedback_samples:
                update_log.append({
                    "level":       "metric",
                    "metric_name": metric_name,
                    "category":    stats.get("category", "unknown"),
                    "action":      "skipped",
                    "reason":      (
                        f"Only {total_w:.1f} decay-weighted sample(s); "
                        f"minimum is {cfg.min_feedback_samples}."
                    ),
                    "old_weight":    old_weight,
                    "new_weight":    old_weight,
                    "confidence":    float(existing.get("confidence", 0.0)),
                    "sample_count":  total_w,
                    "trend":         existing.get("trend", "stable"),
                })
                # Preserve existing state unchanged
                new_metric_weights[metric_name] = {
                    "weight":       old_weight,
                    "confidence":   float(existing.get("confidence", 0.0)),
                    "sample_count": total_w,
                    "trend":        existing.get("trend", "stable"),
                    "category":     stats.get("category", "unknown"),
                }
                continue

            _, new_w, entry = _compute_single_update(
                key=metric_name,
                level="metric",
                total_w=total_w,
                helpful_w=helpful_w,
                delta_w=delta_w,
                old_weight=old_weight,
                prev_weight=old_weight,
                cfg=cfg,
            )
            entry["metric_name"] = metric_name
            entry["category"]    = stats.get("category", "unknown")
            update_log.append(entry)

            # Derive trend from direction of change
            if new_w > old_weight + 1e-6:
                trend = "increasing"
            elif new_w < old_weight - 1e-6:
                trend = "decreasing"
            else:
                trend = "stable"

            confidence = min(1.0, round(total_w / cfg.confidence_sample_target, 4))

            new_metric_weights[metric_name] = {
                "weight":       new_w,
                "confidence":   confidence,
                "sample_count": round(total_w, 4),
                "trend":        trend,
                "category":     stats.get("category", "unknown"),
            }

    return new_weights, update_log, new_metric_weights


def _compute_single_update(
    key: str,
    level: str,
    total_w: float,
    helpful_w: float,
    delta_w: float,
    old_weight: float,
    prev_weight: float,
    cfg: AgentConfig,
) -> tuple[float, float, dict]:
    """
    Core Bayesian nudge computation for one key (category or metric).

    Returns (old_weight, new_weight, log_entry).
    """
    helpfulness_rate = helpful_w / total_w if total_w > 0 else 0.5
    avg_outcome      = delta_w / total_w if total_w > 0 else 0.0
    outcome_signal   = math.tanh(avg_outcome)            # -1 … +1

    # Blend: shift toward outcome signal when outcome data is present.
    outcome_present = abs(delta_w) > OUTCOME_EPSILON
    if outcome_present:
        combined = (
            SUBJECTIVE_BLEND_WEIGHT * helpfulness_rate
            + OUTCOME_BLEND_WEIGHT * (outcome_signal + 1) / 2.0
        )
        blend_note = f"outcome-blended ({OUTCOME_BLEND_WEIGHT:.0%} outcome / {SUBJECTIVE_BLEND_WEIGHT:.0%} subjective)"
    else:
        combined   = helpfulness_rate   # subjective only
        blend_note = "subjective-only (no outcome_delta data)"

    # Confidence-scaled learning rate
    confidence_factor = min(1.0, total_w / cfg.confidence_sample_target)
    effective_rate    = cfg.self_learning_rate * confidence_factor

    nudge = (combined - 0.5) * 2.0 * effective_rate
    new_w = old_weight + old_weight * nudge
    new_w = round(max(cfg.weight_min, min(cfg.weight_max, new_w)), 4)

    direction = (
        "↑ boosted"   if new_w > old_weight else
        ("↓ reduced"  if new_w < old_weight else "→ unchanged")
    )

    entry = {
        "level":               level,
        "key":                 key,
        "action":              "updated",
        "total_feedback_w":    round(total_w, 3),
        "helpful_w":           round(helpful_w, 3),
        "helpfulness_rate":    round(helpfulness_rate, 3),
        "avg_outcome_delta":   round(avg_outcome, 3),
        "outcome_signal":      round(outcome_signal, 3),
        "combined_signal":     round(combined, 3),
        "blend_method":        blend_note,
        "confidence_factor":   round(confidence_factor, 4),
        "effective_rate":      round(effective_rate, 4),
        "nudge":               round(nudge, 4),
        "old_weight":          old_weight,
        "new_weight":          new_w,
        "direction":           direction,
        "reason": (
            f"helpfulness_rate={helpfulness_rate:.1%}, "
            f"avg_outcome={avg_outcome:+.3f} ({blend_note}), "
            f"confidence={confidence_factor:.2f} → effective_rate={effective_rate:.4f}, "
            f"nudge={nudge:+.4f}"
        ),
    }

    return old_weight, new_w, entry
