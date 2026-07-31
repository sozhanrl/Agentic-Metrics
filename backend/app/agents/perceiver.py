"""
Perceiver Agent — Idea #1: Trend-Aware Severity Detection.

Responsibility:
  Convert raw (MetricValue, MetricDefinition) pairs into MetricSignal objects,
  amplifying severity when a metric is *trending in the wrong direction*,
  not just currently off-target.

Trend detection uses simple linear regression over the last N historical
data points. A worsening slope adds up to MAX_TREND_AMPLIFICATION extra
severity beyond the static snapshot, so a metric that is slightly below
target but degrading fast gets flagged earlier than one that is worse but
improving.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.agents.config import AgentConfig, default_config


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MetricSignal:
    """
    Full picture of one metric at one point in time, including trend context.
    Produced by the Perceiver; consumed by Evaluator, Negotiator, Explainer.
    """
    metric_id: int
    key: str
    display_name: str
    category: str
    unit: str | None
    higher_is_better: bool
    value: float
    recorded_at: datetime

    # Perceiver outputs
    severity: float = 0.0         # 0 (fine) → 1+ (bad); can exceed 1 for critical
    deviation_pct: float = 0.0    # signed % from target (positive = bad direction)
    trend_slope: float = 0.0      # units/period; positive = worsening
    trend_direction: str = "flat" # "worsening" | "improving" | "flat"
    trend_amplification: float = 0.0  # extra severity added due to trend

    # Provenance
    agent_steps: list = field(default_factory=list)  # list of AgentStep dicts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _linear_slope(ys: list[float]) -> float:
    """
    Returns the slope of the best-fit line through ys (equally-spaced x = 0,1,2…).
    Positive slope means values are increasing over time.
    Returns 0.0 if fewer than 2 points.
    """
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0


def _classify_slope(slope: float, higher_is_better: bool, threshold: float = 0.05) -> str:
    """
    Map a raw slope to a human-readable direction relative to what's *good*.
    'worsening' means the metric is moving in the bad direction.
    """
    if abs(slope) < threshold:
        return "flat"
    going_up = slope > 0
    if higher_is_better:
        return "improving" if going_up else "worsening"
    else:
        return "worsening" if going_up else "improving"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def perceive(
    value_row,
    definition,
    history: list | None = None,
    cfg: AgentConfig | None = None,
) -> MetricSignal:
    """
    Build a MetricSignal for one metric.

    Parameters
    ----------
    value_row   : MetricValue ORM object (latest value)
    definition  : MetricDefinition ORM object
    history     : list of MetricValue ORM objects for this metric, oldest-first.
                  If None or empty, trend detection is skipped.
    cfg         : AgentConfig. Defaults to module-level defaults if omitted.

    Returns
    -------
    MetricSignal with severity, deviation_pct, trend_slope, trend_direction
    """
    cfg = cfg or default_config()

    key             = definition.key
    value           = float(value_row.value)
    higher_is_better = definition.higher_is_better
    target_def      = cfg.default_targets.get(key)

    signal = MetricSignal(
        metric_id=definition.id,
        key=key,
        display_name=definition.display_name,
        category=definition.category,
        unit=definition.unit,
        higher_is_better=higher_is_better,
        value=value,
        recorded_at=value_row.recorded_at,
    )

    if not target_def:
        # Unknown metric — no scoring model yet, treat as neutral
        signal.agent_steps.append({
            "agent": "Perceiver",
            "action": "skipped",
            "detail": f"No target defined for metric '{key}'; treated as neutral.",
        })
        return signal

    target    = target_def["target"]
    tolerance = target_def["tolerance"]

    # --- Static deviation --------------------------------------------------
    if higher_is_better:
        deviation = target - value          # positive = below target = bad
    else:
        deviation = value - target          # positive = above target = bad

    deviation_pct = (deviation / target * 100) if target else 0.0
    severity      = max(0.0, deviation / tolerance) if tolerance else 0.0

    signal.deviation_pct = round(deviation_pct, 1)
    signal.severity      = round(severity, 2)

    step_base = {
        "agent":  "Perceiver",
        "action": "static-evaluation",
        "detail": (
            f"{definition.display_name}={value}{definition.unit or ''} "
            f"vs target={target}; deviation={deviation_pct:+.1f}%; "
            f"base severity={severity:.2f}"
        ),
    }
    signal.agent_steps.append(step_base)

    # --- Trend detection ---------------------------------------------------
    if history and len(history) >= 2:
        lookback = history[-cfg.trend_lookback:]
        ys = [float(h.value) for h in lookback]
        slope = _linear_slope(ys)
        direction = _classify_slope(slope, higher_is_better)

        signal.trend_slope     = round(slope, 4)
        signal.trend_direction = direction

        if direction == "worsening" and severity > 0:
            # Amplify severity proportional to how fast it's worsening.
            # Normalise slope by current value so the factor is unit-agnostic.
            norm_slope = abs(slope) / (abs(value) or 1.0)
            amplification = min(norm_slope * 2.0, cfg.max_trend_amplification)
            signal.severity       = round(severity * (1 + amplification), 2)
            signal.trend_amplification = round(amplification, 3)

            signal.agent_steps.append({
                "agent":  "Perceiver",
                "action": "trend-amplification",
                "detail": (
                    f"Trend worsening (slope={slope:+.3f}/period); "
                    f"amplification={amplification:.1%}; "
                    f"adjusted severity={signal.severity:.2f}"
                ),
            })
        else:
            signal.agent_steps.append({
                "agent":  "Perceiver",
                "action": "trend-ok",
                "detail": (
                    f"Trend direction='{direction}' (slope={slope:+.3f}/period); "
                    f"no severity amplification applied."
                ),
            })
    else:
        signal.agent_steps.append({
            "agent":  "Perceiver",
            "action": "trend-skipped",
            "detail": "Insufficient history for trend detection (need ≥ 2 points).",
        })

    return signal


def perceive_all(
    metric_rows: list,
    history_map: dict[int, list] | None = None,
    cfg: AgentConfig | None = None,
) -> list[MetricSignal]:
    """
    Run perceive() over all (MetricValue, MetricDefinition) rows in one pass.

    Parameters
    ----------
    metric_rows  : list of (MetricValue, MetricDefinition) tuples
    history_map  : { metric_id: [MetricValue, ...] } oldest-first per metric
    cfg          : AgentConfig
    """
    history_map = history_map or {}
    cfg         = cfg or default_config()
    signals     = []

    for value_row, definition in metric_rows:
        history = history_map.get(definition.id, [])
        signals.append(perceive(value_row, definition, history=history, cfg=cfg))

    return signals
