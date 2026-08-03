"""
Context Detection Engine agent.

Classifies a project's domain (banking, healthcare, gaming, ecommerce, general)
and applies a domain-specific multiplicative overlay on top of category weights.
"""

from typing import Optional, Any

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "banking": ["bank", "finance", "fintech", "payment", "ledger", "trading", "loan"],
    "healthcare": ["health", "clinic", "patient", "medical", "hospital", "pharma", "ehr"],
    "gaming": ["game", "gaming", "unity", "unreal", "multiplayer", "matchmaking"],
    "ecommerce": ["shop", "cart", "checkout", "ecommerce", "retail", "storefront"],
}

DOMAIN_PROFILES: dict[str, dict[str, float]] = {
    "banking":    {"code_quality": 1.15, "process": 0.90, "devops": 1.20},
    "healthcare": {"code_quality": 1.20, "process": 0.95, "devops": 1.15},
    "gaming":     {"code_quality": 1.00, "process": 0.80, "devops": 1.10},
    "ecommerce":  {"code_quality": 1.05, "process": 0.95, "devops": 1.15},
    "general":    {"code_quality": 1.00, "process": 1.00, "devops": 1.00},
}


def detect_domain(
    project: Any = None,
    risk_profile: Any = None,
) -> tuple[str, str, list[str]]:
    """
    Detect project domain based on risk profile override or keyword matching.

    Returns
    -------
    (domain, confidence, matched_keywords)
      domain           : 'banking' | 'healthcare' | 'gaming' | 'ecommerce' | 'general'
      confidence       : 'explicit' | 'detected' | 'default'
      matched_keywords : list of matched keyword strings
    """
    # 1. Check explicit domain in risk_profile
    explicit_domain = None
    if risk_profile:
        explicit_domain = getattr(risk_profile, "domain", None)
        if isinstance(risk_profile, dict):
            explicit_domain = risk_profile.get("domain")

    if explicit_domain and str(explicit_domain).strip():
        dom_lower = str(explicit_domain).strip().lower()
        if dom_lower in DOMAIN_PROFILES:
            return dom_lower, "explicit", []

    # 2. Keyword match against project.name + project.external_id + risk_profile.notes
    text_corpus: list[str] = []
    if project:
        p_name = getattr(project, "name", None) or (project.get("name") if isinstance(project, dict) else "")
        p_ext  = getattr(project, "external_id", None) or (project.get("external_id") if isinstance(project, dict) else "")
        if p_name:
            text_corpus.append(str(p_name))
        if p_ext:
            text_corpus.append(str(p_ext))

    if risk_profile:
        notes = getattr(risk_profile, "notes", None) or (risk_profile.get("notes") if isinstance(risk_profile, dict) else "")
        if notes:
            text_corpus.append(str(notes))

    full_text = " ".join(text_corpus).lower()

    best_domain = "general"
    max_matches = 0
    best_keywords: list[str] = []

    for dom, keywords in DOMAIN_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in full_text]
        if len(matched) > max_matches:
            max_matches = len(matched)
            best_domain = dom
            best_keywords = matched

    if max_matches > 0:
        return best_domain, "detected", best_keywords

    return "general", "default", []


def apply_domain_overlay(
    weights: dict[str, float],
    project: Any = None,
    risk_profile: Any = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    """
    Apply domain multiplicative profile overlay to category weights.

    Returns
    -------
    (new_weights, step_dict)
    """
    domain, confidence, matched_keywords = detect_domain(project, risk_profile)
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])

    new_weights = {}
    for cat, w in weights.items():
        multiplier = profile.get(cat, 1.00)
        new_weights[cat] = round(float(w) * multiplier, 4)

    if confidence == "explicit":
        detail = f"Domain explicitly set to '{domain}' via risk profile. Overlay applied: {profile}."
    elif confidence == "detected":
        detail = f"Auto-detected domain '{domain}' from keywords ({', '.join(matched_keywords)}). Overlay applied: {profile}."
    else:
        detail = f"No domain keywords matched; defaulted to 'general'. Overlay applied: {profile}."

    step_dict = {
        "agent": "ContextDetector",
        "action": f"domain={domain} (confidence={confidence})",
        "detail": detail,
    }

    return new_weights, step_dict
