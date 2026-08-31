"""
Unit tests for Disclosure Safety Serialization.

Verifies that public disclosure mode strictly prevents leakage of:
- Strategy names ('pure_bayesian', 'graph_propagated', 'hybrid')
- Raw Bayesian parameters (alpha, beta, prior variance)
- Causal edge strength numbers and internal graph formulas
- Internal agent provenance trails and adaptive category weights
"""

import os
from app.disclosure import (
    serialize_recommendation_response,
    sanitize_reasoning_trail,
    generate_public_reasoning_summary,
)


def test_public_disclosure_mode_strips_internals():
    raw_payload = {
        "id": 101,
        "project_id": 1,
        "title": "Low Test Coverage on Core Services",
        "explanation": "Test coverage is 55% vs target 80%.",
        "reasoning_trail": [
            "[Perceiver] Test Coverage=55.0% vs target=80; deviation=-31.2%; base severity=1.20",
            "[BayesianLearner] Prior: α₀=5.00, β₀=5.00 (from context memory key 'general')",
            "[BayesianLearner] Posterior: α=7.20, β=4.10 → posterior mean weight=0.6372 (variance=0.0189)",
            "[StrategySelector] Strategy: HYBRID — Hybrid strategy: 58% Bayesian posterior / 42% Causal graph",
            "[CausalGraph] Propagated Causal Influence: test_coverage → change_failure_rate (direct effect, propagated reward +0.1420)",
            "[Explainer] Increasing test coverage directly mitigates change failure rate.",
        ],
        "agent_trail": [
            {"agent": "Perceiver", "action": "static-evaluation", "detail": "Test Coverage=55.0%"},
            {"agent": "StrategySelector", "action": "strategy=hybrid", "detail": "Selected hybrid strategy"},
            {"agent": "AdaptiveWeighter", "action": "tech-debt-adjustment", "detail": "Applied +15% weight"},
        ],
        "adaptive_weights": {"code_quality": 1.15, "process": 0.8, "devops": 1.1},
        "trend_slope": -0.045,
        "conflict_note": "Negotiated penalty 12%",
        "detected_domain": "ecommerce",
        "confidence_score": 0.82,
        "confidence_label": "high",
        "confidence_evidence": [
            "Bayesian evidence sample count: 12.0",
            "Strategy: hybrid",
            "Causal graph confidence: 0.85",
        ],
        "priority_score": 72.0,
        "related_metrics": [1],
        "status": "open",
    }

    # Public mode serialization
    safe = serialize_recommendation_response(raw_payload, disclosure_mode="public")

    # Assert basic public fields remain intact
    assert safe["id"] == 101
    assert safe["title"] == "Low Test Coverage on Core Services"
    assert safe["explanation"] == "Test coverage is 55% vs target 80%."
    assert safe["priority_score"] == 72.0
    assert safe["confidence_label"] == "high"
    assert safe["status"] == "open"
    assert isinstance(safe["reasoning_summary"], str)
    assert len(safe["reasoning_summary"]) > 0

    # Assert all arbitration internals and provenance are stripped
    assert safe["agent_trail"] == []
    assert safe["adaptive_weights"] is None
    assert safe["confidence_score"] is None
    assert safe["confidence_evidence"] == []
    assert safe["conflict_note"] is None
    assert safe["detected_domain"] is None

    # Assert no strategy names or edge math leak in sanitized reasoning trail
    sanitized_text = " ".join(safe["reasoning_trail"]).lower()
    assert "pure_bayesian" not in sanitized_text
    assert "graph_propagated" not in sanitized_text
    assert "hybrid" not in sanitized_text
    assert "posterior" not in sanitized_text
    assert "variance=" not in sanitized_text
    assert "α" not in sanitized_text
    assert "β" not in sanitized_text
    assert "alpha" not in sanitized_text
    assert "beta" not in sanitized_text
    assert "propagated reward" not in sanitized_text
    assert "[strategyselector]" not in sanitized_text
    assert "[bayesianlearner]" not in sanitized_text
    assert "[causalgraph]" not in sanitized_text


def test_full_disclosure_mode_preserves_internals():
    raw_payload = {
        "id": 102,
        "project_id": 1,
        "title": "High Defect Density",
        "explanation": "Defect density is high.",
        "reasoning_trail": ["[StrategySelector] Strategy: PURE_BAYESIAN"],
        "agent_trail": [{"agent": "StrategySelector", "action": "pure_bayesian"}],
        "adaptive_weights": {"code_quality": 1.2},
        "confidence_score": 0.88,
        "confidence_label": "high",
        "confidence_evidence": ["Sample count: 35"],
        "priority_score": 80.0,
    }

    full = serialize_recommendation_response(raw_payload, disclosure_mode="full")

    # In full mode, internals are preserved for debugging/dev
    assert len(full["agent_trail"]) == 1
    assert full["adaptive_weights"] == {"code_quality": 1.2}
    assert full["confidence_score"] == 0.88
    assert len(full["confidence_evidence"]) == 1
    assert "[StrategySelector]" in full["reasoning_trail"][0]
