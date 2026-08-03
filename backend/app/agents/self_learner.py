"""
Self-Learning Module — Feedback-Driven Bayesian Beta-Bernoulli Weight Updates.

This module replaces heuristic weight updates with a statistically principled
Beta-Bernoulli Bayesian posterior update model while remaining 100% backward
compatible with the existing recommendation pipeline and admin routes.

Mathematical Model
------------------
1. Beta Prior:
   For base weight w0 (normalized to [0,1]):
     alpha0 = w0 * PRIOR_STRENGTH
     beta0  = (1 - w0) * PRIOR_STRENGTH

2. Posterior Update:
   For feedback signal (combined_score in [0, 1]):
     If combined_score > 0.5:
         alpha += (combined_score - 0.5) * 2.0 * effective_weight
     Else:
         beta  += (0.5 - combined_score) * 2.0 * effective_weight

3. Posterior Mean Weight:
   posterior_mean = alpha / (alpha + beta)
   learned_weight = clamp(posterior_mean * 2.0, WEIGHT_MIN, WEIGHT_MAX)

4. Posterior Variance Confidence:
   variance = (alpha * beta) / ((alpha + beta)^2 * (alpha + beta + 1))
   confidence = clamp(1.0 - variance * 5.0, 0.0, 1.0)

5. Shrinkage Regularization:
   alpha += REGULARIZATION_RATE * (alpha0 - alpha)
   beta  += REGULARIZATION_RATE * (beta0  - beta)
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
    Compute updated category weights AND per-metric weight adjustments using
    Bayesian Beta-Bernoulli learning.

    Parameters
    ----------
    feedback_summary : { category: { "total_w": float, "helpful_w": float,
                                      "outcome_delta_sum_w": float } }
    current_weights  : Current category weights (starting point).
    metric_feedback_summary : { metric_name: { "total_w": float, "helpful_w": float,
                                               "outcome_delta_sum_w": float,
                                               "category": str } }
    current_metric_weights : { metric_name: { "weight": float, "confidence": float,
                                              "sample_count": float, "trend": str,
                                              "alpha": float, "beta": float } }
    cfg              : AgentConfig

    Returns
    -------
    (new_category_weights, update_log, new_metric_weights)
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
                "level":      "category",
                "category":   category,
                "key":        category,
                "action":     "skipped",
                "reason":     (
                    f"Only {total_w:.1f} decay-weighted feedback sample(s); "
                    f"minimum is {cfg.min_feedback_samples}."
                ),
                "old_weight": current_weights.get(category, 1.0),
                "new_weight": current_weights.get(category, 1.0),
            })
            continue

        old_w, new_w, entry = _compute_bayesian_single_update(
            key=category,
            level="category",
            total_w=float(total_w),
            helpful_w=float(helpful_w),
            delta_w=float(delta_w),
            old_weight=current_weights.get(category, 1.0),
            existing_state={},
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

            existing   = current_metric_weights.get(metric_name, {})
            old_weight = float(existing.get("weight", 1.0))
            alpha_val  = float(existing.get("alpha", 5.0))
            beta_val   = float(existing.get("beta", 5.0))

            if total_w < cfg.min_feedback_samples:
                update_log.append({
                    "level":       "metric",
                    "metric_name": metric_name,
                    "key":         metric_name,
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
                    "alpha":         alpha_val,
                    "beta":          beta_val,
                })
                # Preserve existing state unchanged
                new_metric_weights[metric_name] = {
                    "weight":       old_weight,
                    "confidence":   float(existing.get("confidence", 0.0)),
                    "sample_count": total_w,
                    "trend":        existing.get("trend", "stable"),
                    "category":     stats.get("category", "unknown"),
                    "alpha":        alpha_val,
                    "beta":         beta_val,
                    "alpha0":       float(existing.get("alpha0", alpha_val)),
                    "beta0":        float(existing.get("beta0", beta_val)),
                }
                continue

            _, new_w, entry = _compute_bayesian_single_update(
                key=metric_name,
                level="metric",
                total_w=total_w,
                helpful_w=helpful_w,
                delta_w=delta_w,
                old_weight=old_weight,
                existing_state=existing,
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

            new_metric_weights[metric_name] = {
                "weight":       new_w,
                "confidence":   entry["confidence"],
                "sample_count": round(total_w, 4),
                "trend":        trend,
                "category":     stats.get("category", "unknown"),
                "alpha":        entry["alpha"],
                "beta":         entry["beta"],
                "alpha0":       entry["alpha0"],
                "beta0":        entry["beta0"],
            }

    return new_weights, update_log, new_metric_weights


def _compute_bayesian_single_update(
    key: str,
    level: str,
    total_w: float,
    helpful_w: float,
    delta_w: float,
    old_weight: float,
    existing_state: dict,
    cfg: AgentConfig,
) -> tuple[float, float, dict]:
    """
    Core Beta-Bernoulli Bayesian update for one key (category or metric).
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

    # Base weight normalized to [0, 1] range (where 1.0 weight maps to 0.5)
    norm_w0 = max(0.05, min(0.95, old_weight / 2.0))
    alpha0  = float(existing_state.get("alpha0", norm_w0 * cfg.prior_strength))
    beta0   = float(existing_state.get("beta0", (1.0 - norm_w0) * cfg.prior_strength))

    # Existing alpha/beta state or initialize from prior
    alpha = float(existing_state.get("alpha", alpha0))
    beta  = float(existing_state.get("beta", beta0))

    # Confidence scaling factor based on evidence volume
    confidence_factor = min(1.0, total_w / cfg.confidence_sample_target)

    # Bayesian posterior update step
    if combined > 0.5:
        alpha += (combined - 0.5) * 2.0 * total_w * confidence_factor * 0.1
    else:
        beta  += (0.5 - combined) * 2.0 * total_w * confidence_factor * 0.1

    # Apply regularization (shrinkage toward prior to prevent permanent drift)
    alpha += cfg.regularization_rate * (alpha0 - alpha)
    beta  += cfg.regularization_rate * (beta0  - beta)

    # Prevent non-positive values
    alpha = max(0.1, alpha)
    beta  = max(0.1, beta)

    # Compute posterior mean and variance
    total_ab = alpha + beta
    posterior_mean = alpha / total_ab
    variance = (alpha * beta) / ((total_ab ** 2) * (total_ab + 1))

    # Compute mathematical confidence from variance (clamped to [0, 1])
    confidence = round(max(0.0, min(1.0, 1.0 - variance * 5.0)), 4)

    # Map posterior mean (0..1) to learned weight range (0.3 .. 2.0)
    new_w = posterior_mean * 2.0
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
        "confidence":          confidence,
        "posterior_mean":      round(posterior_mean, 4),
        "posterior_variance":  round(variance, 6),
        "alpha":               round(alpha, 4),
        "beta":                round(beta, 4),
        "alpha0":              round(alpha0, 4),
        "beta0":               round(beta0, 4),
        "old_weight":          old_weight,
        "new_weight":          new_w,
        "direction":           direction,
        "reason": (
            f"Beta posterior mean={posterior_mean:.4f} (α={alpha:.2f}, β={beta:.2f}), "
            f"variance={variance:.5f} → confidence={confidence:.2f}, "
            f"helpfulness={helpfulness_rate:.1%}, blend={blend_note}"
        ),
    }

    return old_weight, new_w, entry
