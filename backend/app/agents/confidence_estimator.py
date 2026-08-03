"""
Confidence Estimator agent.

Attaches an explainable confidence score (0.0 to 1.0) and confidence label
('high' | 'medium' | 'low') to every recommendation, distinct from priority_score.
"""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class DependencySupport:
    """Dataclass representing a discovered upstream metric dependency."""
    edge_confidence: str  # "high" | "medium" | "low"
    correlation: float = 0.0


@dataclass
class ConfidenceResult:
    """Confidence evaluation output for one recommendation."""
    score: float
    label: str            # "high" | "medium" | "low"
    evidence: list[str] = field(default_factory=list)


def estimate_confidence(
    signal: Any,
    weight_sample_size: float = 0.0,
    conflict_note: Optional[str] = None,
    dependency_support: Optional[Any] = None,
) -> ConfidenceResult:
    """
    Estimate explainable confidence score and evidence breakdown.

    Parameters
    ----------
    signal             : MetricSignal object or dict
    weight_sample_size : number of feedback samples backing category's weight
    conflict_note      : non-None if Negotiator resolved a conflict
    dependency_support : DependencySupport object, dict, or None

    Returns
    -------
    ConfidenceResult(score, label, evidence)
    """
    evidence: list[str] = []

    # 1. Severity margin factor (weight 0.35)
    sev = float(getattr(signal, "severity", 0.0) if not isinstance(signal, dict) else signal.get("severity", 0.0))
    sev_factor = min(1.0, max(0.0, (sev - 0.3) / (2.0 - 0.3)))
    sev_contrib = 0.35 * sev_factor
    evidence.append(f"Severity margin (severity={sev:.2f}): +{sev_contrib:.2f} (weight 0.35)")

    # 2. Weight evidence factor (weight 0.25)
    n_samples = float(weight_sample_size or 0.0)
    sample_factor = min(1.0, max(0.0, n_samples / 50.0))
    sample_contrib = 0.25 * sample_factor
    evidence.append(f"Weight evidence ({n_samples:.1f} samples): +{sample_contrib:.2f} (weight 0.25)")

    # 3. Negotiation penalty factor (-0.20)
    if conflict_note:
        penalty_contrib = -0.20
        evidence.append("Negotiation penalty: -0.20 (contested near-tie resolved by Negotiator)")
    else:
        penalty_contrib = 0.0
        evidence.append("Negotiation penalty: 0.00 (uncontested priority)")

    # 4. Dependency support bonus factor (+0.20 full / +0.10 half)
    dep_contrib = 0.0
    if dependency_support:
        edge_conf = getattr(dependency_support, "edge_confidence", None)
        if isinstance(dependency_support, dict):
            edge_conf = dependency_support.get("edge_confidence") or dependency_support.get("confidence")
        elif edge_conf is None:
            edge_conf = getattr(dependency_support, "confidence", None)

        if edge_conf == "high":
            dep_contrib = 0.20
            evidence.append("Dependency support bonus: +0.20 (high-confidence upstream dependency)")
        elif edge_conf == "medium":
            dep_contrib = 0.10
            evidence.append("Dependency support bonus: +0.10 (medium-confidence upstream dependency)")
        else:
            evidence.append("Dependency support bonus: 0.00 (low/no confidence upstream dependency)")
    else:
        evidence.append("Dependency support bonus: 0.00 (no upstream metric dependency)")

    # Final score calculation
    raw_score = sev_contrib + sample_contrib + penalty_contrib + dep_contrib
    score = round(max(0.0, min(1.0, raw_score)), 2)

    if score >= 0.70:
        label = "high"
    elif score >= 0.45:
        label = "medium"
    else:
        label = "low"

    return ConfidenceResult(score=score, label=label, evidence=evidence)
