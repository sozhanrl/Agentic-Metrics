"""
Adaptive Weighting Engine — Idea #3: Context-Aware Category Weights.

Responsibility:
  Given a project's risk profile and its persisted weight history, compute a
  set of category weights that reflect the project's *current context* rather
  than the universal base priors.

  The adjustments are deterministic and fully explainable: every delta is
  attributed to a specific risk-profile attribute with a logged reason.

Rules applied (in order, multiplicative):
  1. Tech-debt index   → boosts code_quality weight
  2. Risk tolerance    → adjusts devops weight (low tolerance = tighten devops)
  3. Team size         → small teams get a process weight reduction
  4. Historical weights→ if self-learning has already nudged weights for this
                         project, those form the starting point rather than
                         the universal BASE_CATEGORY_WEIGHTS.
"""

from app.agents.config import (
    AgentConfig, default_config,
    TECH_DEBT_CODE_QUALITY_BOOST,
    RISK_TOLERANCE_DEVOPS_FACTOR,
    SMALL_TEAM_PROCESS_FACTOR,
    SMALL_TEAM_THRESHOLD,
)


def _tech_debt_bucket(index: float) -> str:
    """Map a 0-1 tech_debt_index to a named bucket."""
    if index < 0.35:
        return "low"
    if index <= 0.65:
        return "medium"
    return "high"


def compute_adaptive_weights(
    base_weights: dict[str, float],
    risk_profile=None,          # ProjectRiskProfile ORM object or None
    cfg: AgentConfig | None = None,
) -> tuple[dict[str, float], list[dict]]:
    """
    Compute context-aware category weights.

    Parameters
    ----------
    base_weights  : Starting weights — typically the latest persisted weights
                    for the project (from crud.get_latest_weights), or
                    BASE_CATEGORY_WEIGHTS if no history exists.
    risk_profile  : ProjectRiskProfile ORM object, or None (uses neutral defaults).
    cfg           : AgentConfig

    Returns
    -------
    (adjusted_weights, agent_steps)
      adjusted_weights : dict[str, float] — final weights, clamped to [weight_min, weight_max]
      agent_steps      : list of agent step dicts for the provenance trail
    """
    cfg    = cfg or default_config()
    steps  = []
    w      = dict(base_weights)   # mutable copy

    if risk_profile is None:
        steps.append({
            "agent":  "AdaptiveWeighter",
            "action": "no-profile",
            "detail": "No risk profile found for project; using base weights unchanged.",
        })
        return _clamp(w, cfg), steps

    # -----------------------------------------------------------------------
    # Rule 1: Tech-debt index → code_quality boost
    # -----------------------------------------------------------------------
    tech_debt = float(risk_profile.tech_debt_index or 0.5)
    bucket    = _tech_debt_bucket(tech_debt)
    factor    = TECH_DEBT_CODE_QUALITY_BOOST[bucket]
    old_cq    = w.get("code_quality", 1.0)
    w["code_quality"] = round(old_cq * factor, 4)
    steps.append({
        "agent":  "AdaptiveWeighter",
        "action": "tech-debt-adjustment",
        "detail": (
            f"tech_debt_index={tech_debt:.2f} → bucket='{bucket}'; "
            f"code_quality weight {old_cq} × {factor} = {w['code_quality']}"
        ),
    })

    # -----------------------------------------------------------------------
    # Rule 2: Risk tolerance → devops weight
    # -----------------------------------------------------------------------
    tolerance = (risk_profile.risk_tolerance or "medium").lower()
    if tolerance not in RISK_TOLERANCE_DEVOPS_FACTOR:
        tolerance = "medium"
    dev_factor = RISK_TOLERANCE_DEVOPS_FACTOR[tolerance]
    old_dv     = w.get("devops", 1.1)
    w["devops"] = round(old_dv * dev_factor, 4)
    steps.append({
        "agent":  "AdaptiveWeighter",
        "action": "risk-tolerance-adjustment",
        "detail": (
            f"risk_tolerance='{tolerance}'; "
            f"devops weight {old_dv} × {dev_factor} = {w['devops']}"
        ),
    })

    # -----------------------------------------------------------------------
    # Rule 3: Small team → process weight reduction
    # -----------------------------------------------------------------------
    team_size = risk_profile.team_size
    if team_size is not None and team_size <= SMALL_TEAM_THRESHOLD:
        old_proc   = w.get("process", 0.8)
        w["process"] = round(old_proc * SMALL_TEAM_PROCESS_FACTOR, 4)
        steps.append({
            "agent":  "AdaptiveWeighter",
            "action": "small-team-adjustment",
            "detail": (
                f"team_size={team_size} ≤ {SMALL_TEAM_THRESHOLD}; "
                f"process weight {old_proc} × {SMALL_TEAM_PROCESS_FACTOR} = {w['process']}"
            ),
        })
    else:
        steps.append({
            "agent":  "AdaptiveWeighter",
            "action": "team-size-ok",
            "detail": (
                f"team_size={'N/A' if team_size is None else team_size}; "
                f"no process weight adjustment needed."
            ),
        })

    return _clamp(w, cfg), steps


def _clamp(weights: dict[str, float], cfg: AgentConfig) -> dict[str, float]:
    """Ensure no weight drifts outside [weight_min, weight_max]."""
    return {
        cat: round(max(cfg.weight_min, min(cfg.weight_max, w)), 4)
        for cat, w in weights.items()
    }
