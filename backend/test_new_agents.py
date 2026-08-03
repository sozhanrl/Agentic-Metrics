"""
Verification script for Context Detection Engine and Confidence Estimator.
"""
from types import SimpleNamespace
import sys

from app.agents.context_detector import detect_domain, apply_domain_overlay
from app.agents.confidence_estimator import estimate_confidence, DependencySupport
from app.agents.perceiver import MetricSignal
from app.agents.orchestrator import run_pipeline, EnrichedRecommendation

def test_context_detector():
    print("=" * 60)
    print("TEST 1: Context Detection Engine")
    print("=" * 60)

    # Test (a): Project named "SecurePay Banking Core"
    proj_banking = SimpleNamespace(name="SecurePay Banking Core", external_id="secpay-core")
    domain, conf, kw = detect_domain(proj_banking)
    print(f"Project 'SecurePay Banking Core':")
    print(f"  Detected domain : {domain}")
    print(f"  Confidence      : {conf}")
    print(f"  Matched keywords: {kw}")
    assert domain == "banking", f"Expected banking, got {domain}"
    assert conf == "detected"

    # Test explicit override
    risk_explicit = SimpleNamespace(domain="healthcare", notes="No keywords here")
    domain_exp, conf_exp, kw_exp = detect_domain(proj_banking, risk_explicit)
    print(f"\nExplicit override risk profile (domain='healthcare'):")
    print(f"  Domain    : {domain_exp}")
    print(f"  Confidence: {conf_exp}")
    assert domain_exp == "healthcare"
    assert conf_exp == "explicit"

    # Test default general domain
    proj_gen = SimpleNamespace(name="My Internal Utility", external_id="util-123")
    domain_gen, conf_gen, kw_gen = detect_domain(proj_gen)
    print(f"\nUnmatched project ('My Internal Utility'):")
    print(f"  Domain    : {domain_gen}")
    print(f"  Confidence: {conf_gen}")
    assert domain_gen == "general"
    assert conf_gen == "default"

    # Test overlay weights
    base_w = {"code_quality": 1.0, "process": 1.0, "devops": 1.0}
    overlay_w, step = apply_domain_overlay(base_w, proj_banking)
    print(f"\nOverlay result for banking:")
    print(f"  New weights: {overlay_w}")
    print(f"  Agent step : {step}")
    assert overlay_w["code_quality"] == 1.15
    assert overlay_w["devops"] == 1.20

    print("\n[OK] Context Detection Engine tests PASSED!")

def test_confidence_estimator():
    print("\n" + "=" * 60)
    print("TEST 2: Confidence Estimator")
    print("=" * 60)

    signal = MetricSignal(
        metric_id=101,
        key="test_coverage",
        display_name="Test Coverage",
        category="code_quality",
        value=45.0,
        recorded_at=datetime.now(),
        severity=1.2,  # same severity
        unit="%",
        higher_is_better=True,
    )

    # Rec A: sample size = 0 (no feedback yet)
    conf_a = estimate_confidence(
        signal=signal,
        weight_sample_size=0,
        conflict_note=None,
        dependency_support=None,
    )

    # Rec B: sample size = 50 (well-supported by feedback)
    conf_b = estimate_confidence(
        signal=signal,
        weight_sample_size=50,
        conflict_note=None,
        dependency_support=None,
    )

    # Rec C: sample size = 50 + high dependency support
    dep_high = DependencySupport(edge_confidence="high", correlation=0.85)
    conf_c = estimate_confidence(
        signal=signal,
        weight_sample_size=50,
        conflict_note=None,
        dependency_support=dep_high,
    )

    print("Recommendation A (0 feedback samples):")
    print(f"  Score   : {conf_a.score}")
    print(f"  Label   : {conf_a.label}")
    print(f"  Evidence: {conf_a.evidence}")

    print("\nRecommendation B (50 feedback samples):")
    print(f"  Score   : {conf_b.score}")
    print(f"  Label   : {conf_b.label}")
    print(f"  Evidence: {conf_b.evidence}")

    print("\nRecommendation C (50 feedback samples + High Dependency Support):")
    print(f"  Score   : {conf_c.score}")
    print(f"  Label   : {conf_c.label}")
    print(f"  Evidence: {conf_c.evidence}")

    assert conf_b.score > conf_a.score, "Rec B with 50 samples should have higher confidence score than Rec A with 0 samples"
    assert conf_c.score > conf_b.score, "Rec C with high dependency support should have higher score than Rec B"
    print("\n[OK] Confidence Estimator tests PASSED!")

def test_full_pipeline_end_to_end():
    print("\n" + "=" * 60)
    print("TEST 3: Orchestrator Pipeline End-to-End Test")
    print("=" * 60)

    proj = SimpleNamespace(name="SecurePay Banking Core", external_id="secpay-core")

    from datetime import datetime
    metric_val_1 = SimpleNamespace(
        id=1, project_id=1, metric_id=10, value=40.0, recorded_at=datetime.now()
    )
    metric_def_1 = SimpleNamespace(
        id=10, key="test_coverage", display_name="Test Coverage",
        category="code_quality", source="sonarqube", unit="%", higher_is_better=True
    )

    metric_val_2 = SimpleNamespace(
        id=2, project_id=1, metric_id=20, value=25.0, recorded_at=datetime.now()
    )
    metric_def_2 = SimpleNamespace(
        id=20, key="deployment_frequency", display_name="Deployment Frequency",
        category="devops", source="github", unit="deploys/wk", higher_is_better=True
    )

    metric_rows = [(metric_val_1, metric_def_1), (metric_val_2, metric_def_2)]
    weight_sample_sizes = {"code_quality": 5.0, "devops": 45.0}

    results = run_pipeline(
        metric_rows=metric_rows,
        project=proj,
        weight_sample_sizes=weight_sample_sizes,
    )

    print(f"Pipeline returned {len(results)} recommendations:")
    for i, rec in enumerate(results):
        print(f"\n  Rec #{i+1}: {rec.title}")
        print(f"    priority_score  : {rec.priority_score}")
        print(f"    detected_domain : {rec.detected_domain}")
        print(f"    confidence_score: {rec.confidence_score} ({rec.confidence_label})")
        print(f"    confidence_evidence: {rec.confidence_evidence}")
        print(f"    reasoning_trail:")
        for line in rec.reasoning_trail:
            print(f"      {line}")
        print(f"    agent_trail ({len(rec.agent_trail)} steps):")
        for step in rec.agent_trail:
            print(f"      [{step['agent']}] {step['action']}: {step['detail']}")

    assert len(results) > 0
    assert results[0].detected_domain == "banking"
    print("\n[OK] Pipeline End-to-End test PASSED!")

if __name__ == "__main__":
    test_context_detector()
    test_confidence_estimator()
    test_full_pipeline_end_to_end()
