"""
Disclosure Safety Module.

Controls exposure of internal arbitration mechanisms and Bayesian/Causal provenance:
- public (default): Strips internal agent_trail, adaptive_weights, strategy names,
  raw Bayesian parameters, and edge strength values. Exposes high-level explanation,
  priority_score, confidence_label, action plan, and safe human-readable reasoning summaries.
- full: Returns complete debugging provenance (for local development and internal review).

This strictly governs API response serialization and does NOT alter pipeline computation.
"""

import os
import re
from typing import Any, Optional

DISCLOSURE_MODE_ENV = "DISCLOSURE_MODE"
DEFAULT_DISCLOSURE_MODE = "public"


def get_disclosure_mode() -> str:
    """Return active disclosure mode: 'public' or 'full'."""
    return os.getenv(DISCLOSURE_MODE_ENV, DEFAULT_DISCLOSURE_MODE).strip().lower()


def is_full_disclosure() -> bool:
    """Check if full internal debugging disclosure is enabled."""
    return get_disclosure_mode() == "full"


def sanitize_reasoning_trail(trail: list[str]) -> list[str]:
    """
    Sanitize reasoning trail lines for public disclosure.
    Strips internal strategy tags, edge weights, alpha/beta parameters, and mathematical formulas.
    """
    if is_full_disclosure():
        return list(trail)

    safe_lines = []
    # Patterns matching internal provenance / patent arbitration internals
    forbidden_patterns = [
        re.compile(r"\[BayesianLearner\]", re.IGNORECASE),
        re.compile(r"\[StrategySelector\]", re.IGNORECASE),
        re.compile(r"\[CausalGraph\]", re.IGNORECASE),
        re.compile(r"\[ContextMemoryEngine\]", re.IGNORECASE),
        re.compile(r"alpha|beta|α|β|variance=|posterior|prior|eigenvector", re.IGNORECASE),
        re.compile(r"pure_bayesian|graph_propagated|hybrid", re.IGNORECASE),
        re.compile(r"propagated reward|edge_strength|causal_confidence", re.IGNORECASE),
    ]

    for line in trail:
        # Check if line contains internal arbitration formulas or strategy names
        if any(pat.search(line) for pat in forbidden_patterns):
            continue
        # Strip internal agent prefixes if present
        clean_line = re.sub(r"^\[\w+\]\s*", "", line)
        if clean_line.strip():
            safe_lines.append(clean_line.strip())

    return safe_lines


def generate_public_reasoning_summary(title: str, explanation: str, trail: list[str]) -> str:
    """
    Generate a concise human-readable 1-2 sentence reasoning summary for public consumption.
    """
    safe_lines = sanitize_reasoning_trail(trail)
    if safe_lines:
        return safe_lines[0]
    return explanation.split(".")[0] + "." if "." in explanation else explanation


def serialize_recommendation_response(
    rec_dict: dict[str, Any],
    disclosure_mode: Optional[str] = None,
) -> dict[str, Any]:
    """
    Serialize a recommendation payload according to the active disclosure mode.
    """
    mode = (disclosure_mode or get_disclosure_mode()).lower()

    if mode == "full":
        return rec_dict

    # In public mode: strip provenance internals
    safe_dict = dict(rec_dict)
    
    # 1. Strip raw agent trails & adaptive weights
    safe_dict["agent_trail"] = []
    safe_dict["adaptive_weights"] = None
    
    # 2. Convert confidence score to label only
    safe_dict["confidence_score"] = None
    safe_dict["confidence_evidence"] = []

    # 3. Sanitize reasoning trail and provide safe summary
    raw_trail = rec_dict.get("reasoning_trail") or []
    safe_dict["reasoning_trail"] = sanitize_reasoning_trail(raw_trail)
    safe_dict["reasoning_summary"] = generate_public_reasoning_summary(
        rec_dict.get("title", ""),
        rec_dict.get("explanation", ""),
        raw_trail,
    )

    # 4. Strip strategy or internal conflict notes if present
    safe_dict["conflict_note"] = None
    safe_dict["detected_domain"] = None

    return safe_dict
