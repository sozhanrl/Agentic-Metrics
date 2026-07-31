"""
Pure-function unit tests for self_learner.compute_weight_updates().

These tests require NO database, NO running server, and NO external dependencies.
They verify the mathematical properties of the learning algorithm:

    1. Clamping bounds — weight never escapes [WEIGHT_MIN, WEIGHT_MAX]
    2. Direction correctness — positive feedback → weight increase, negative → decrease
    3. Confidence scaling — effective rate proportional to sample volume
    4. Outcome blending — outcome_delta shifts the update relative to subjective-only
    5. Recency decay passthrough — decayed totals cause smaller updates than raw counts
    6. Category fallback prior — metric-level learning falls back when samples < min
    7. Convergence — repeated positive feedback converges weight near WEIGHT_MAX
    8. Neutral feedback — combined ≈ 0.5 → nudge ≈ 0 → weight barely changes
    9. Per-metric granularity — two metrics in same category can diverge

Run with:
    cd backend
    python -m pytest tests/test_self_learner.py -v
"""

import math
import sys
import os

# Allow running from backend/ or from tests/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.self_learner import compute_weight_updates, _compute_single_update
from app.agents.config import AgentConfig, WEIGHT_MIN, WEIGHT_MAX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cfg(**overrides) -> AgentConfig:
    """Return a fresh AgentConfig with optional overrides for testing."""
    cfg = AgentConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def category_feedback(total_w, helpful_w, delta_w=0.0) -> dict:
    """Build a feedback_summary dict for one category."""
    return {
        "code_quality": {
            "total_w": total_w,
            "helpful_w": helpful_w,
            "outcome_delta_sum_w": delta_w,
        }
    }


def metric_feedback(metric_name, total_w, helpful_w, delta_w=0.0, category="code_quality") -> dict:
    """Build a metric_feedback_summary dict for one metric."""
    return {
        metric_name: {
            "total_w": total_w,
            "helpful_w": helpful_w,
            "outcome_delta_sum_w": delta_w,
            "category": category,
        }
    }


# ---------------------------------------------------------------------------
# Test 1 — Clamping bounds
# ---------------------------------------------------------------------------

class TestClampingBounds:
    """Weight must NEVER drift outside [WEIGHT_MIN, WEIGHT_MAX]."""

    def test_extreme_positive_feedback_clamped_at_max(self):
        cfg = make_cfg(weight_max=2.0, weight_min=0.3, min_feedback_samples=1)
        # 100% helpful, 1000 samples — would push weight to infinity without clamping
        fb  = category_feedback(total_w=1000, helpful_w=1000, delta_w=500)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.9}, cfg=cfg)
        assert new_weights["code_quality"] <= WEIGHT_MAX, (
            f"Expected weight ≤ {WEIGHT_MAX}, got {new_weights['code_quality']}"
        )

    def test_extreme_negative_feedback_clamped_at_min(self):
        cfg = make_cfg(weight_max=2.0, weight_min=0.3, min_feedback_samples=1)
        # 0% helpful, 1000 samples — would push weight to 0 without clamping
        fb  = category_feedback(total_w=1000, helpful_w=0, delta_w=-500)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 0.35}, cfg=cfg)
        assert new_weights["code_quality"] >= WEIGHT_MIN, (
            f"Expected weight ≥ {WEIGHT_MIN}, got {new_weights['code_quality']}"
        )

    def test_custom_clamp_bounds_respected(self):
        cfg = make_cfg(weight_max=1.5, weight_min=0.5, min_feedback_samples=1,
                       self_learning_rate=1.0, confidence_sample_target=1)
        fb  = category_feedback(total_w=100, helpful_w=100, delta_w=100)
        new_weights, _, _ = compute_weight_updates(fb, {"code_quality": 1.4}, cfg=cfg)
        assert new_weights["code_quality"] <= 1.5


# ---------------------------------------------------------------------------
# Test 2 — Direction correctness
# ---------------------------------------------------------------------------

class TestDirectionCorrectness:
    """Positive feedback must increase weight; negative must decrease it."""

    def test_all_helpful_increases_weight(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=10)
        old = {"code_quality": 1.0}
        new_weights, log, _ = compute_weight_updates(fb, old, cfg=cfg)
        assert new_weights["code_quality"] > 1.0, "All-helpful feedback must increase weight"

    def test_no_helpful_decreases_weight(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=0)
        old = {"code_quality": 1.0}
        new_weights, log, _ = compute_weight_updates(fb, old, cfg=cfg)
        assert new_weights["code_quality"] < 1.0, "Zero-helpful feedback must decrease weight"

    def test_update_log_direction_field(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=10)
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        assert len(updated) == 1
        assert updated[0]["direction"] == "↑ boosted"

    def test_mixed_feedback_neutral(self):
        """50% helpful → combined ≈ 0.5 → nudge ≈ 0 → weight barely changes."""
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10,
                       self_learning_rate=0.08)
        fb  = category_feedback(total_w=10, helpful_w=5)
        old = {"code_quality": 1.0}
        new_weights, _, _ = compute_weight_updates(fb, old, cfg=cfg)
        # With 50% helpful and no outcome delta, combined = 0.5 → nudge = 0
        assert abs(new_weights["code_quality"] - 1.0) < 0.001, (
            "50% helpful should produce near-zero nudge"
        )


# ---------------------------------------------------------------------------
# Test 3 — Confidence scaling
# ---------------------------------------------------------------------------

class TestConfidenceScaling:
    """Effective learning rate must scale with evidence volume."""

    def test_low_samples_move_less_than_high_samples(self):
        cfg_low  = make_cfg(min_feedback_samples=1, confidence_sample_target=30,
                            self_learning_rate=0.08)
        cfg_high = make_cfg(min_feedback_samples=1, confidence_sample_target=30,
                            self_learning_rate=0.08)

        fb_low  = category_feedback(total_w=3,  helpful_w=3)   # 3 samples → factor = 3/30 = 0.1
        fb_high = category_feedback(total_w=30, helpful_w=30)  # 30 samples → factor = 1.0

        old = {"code_quality": 1.0}
        new_low,  _, _ = compute_weight_updates(fb_low,  dict(old), cfg=cfg_low)
        new_high, _, _ = compute_weight_updates(fb_high, dict(old), cfg=cfg_high)

        delta_low  = abs(new_low["code_quality"]  - 1.0)
        delta_high = abs(new_high["code_quality"] - 1.0)
        assert delta_high > delta_low, (
            f"High-evidence update ({delta_high:.4f}) must exceed low-evidence ({delta_low:.4f})"
        )

    def test_confidence_factor_logged(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30)
        fb  = category_feedback(total_w=15, helpful_w=15)  # → factor = 0.5
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        assert len(updated) == 1
        assert abs(updated[0]["confidence_factor"] - 0.5) < 0.01, (
            f"Expected confidence_factor ≈ 0.5, got {updated[0]['confidence_factor']}"
        )

    def test_effective_rate_in_log(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30,
                       self_learning_rate=0.08)
        fb  = category_feedback(total_w=15, helpful_w=15)
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        expected = 0.08 * (15 / 30)   # 0.04
        assert abs(updated[0]["effective_rate"] - expected) < 0.001


# ---------------------------------------------------------------------------
# Test 4 — Outcome signal blending
# ---------------------------------------------------------------------------

class TestOutcomeBlending:
    """When outcome_delta is present it should drive more weight change than subjective alone."""

    def test_positive_outcome_amplifies_positive_feedback(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10,
                       self_learning_rate=0.08)
        # Moderately helpful (70%) but strongly confirmed by outcome
        fb_subjective = category_feedback(total_w=10, helpful_w=7, delta_w=0.0)
        fb_outcome    = category_feedback(total_w=10, helpful_w=7, delta_w=5.0)

        old = {"code_quality": 1.0}
        subj_weights, _, _ = compute_weight_updates(fb_subjective, dict(old), cfg=cfg)
        out_weights,  _, _ = compute_weight_updates(fb_outcome,    dict(old), cfg=cfg)

        assert out_weights["code_quality"] > subj_weights["code_quality"], (
            "Positive outcome_delta must amplify the weight update vs subjective-only"
        )

    def test_negative_outcome_overrides_positive_opinion(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10,
                       self_learning_rate=0.08)
        # People said "helpful" but metric got worse → outcome should dominate
        fb = category_feedback(total_w=10, helpful_w=9, delta_w=-5.0)
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        # combined < 0.5 because outcome_signal is strongly negative
        assert updated[0]["combined_signal"] < 0.5, (
            "Strongly negative outcome must pull combined signal below 0.5"
        )

    def test_blend_note_in_log_when_outcome_present(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=8, delta_w=2.0)
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        assert "outcome-blended" in updated[0]["blend_method"]

    def test_blend_note_subjective_when_no_outcome(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=8, delta_w=0.0)
        _, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        updated = [e for e in log if e["action"] == "updated"]
        assert "subjective-only" in updated[0]["blend_method"]


# ---------------------------------------------------------------------------
# Test 5 — Recency decay passthrough
# ---------------------------------------------------------------------------

class TestRecencyDecayPassthrough:
    """
    Decay is applied in crud.py before calling compute_weight_updates().
    Here we simulate that by passing in pre-decayed totals and verifying
    that lower total_w (mimicking heavy decay) produces a smaller update.
    """

    def test_decayed_totals_produce_smaller_update_than_raw(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30,
                       self_learning_rate=0.08)

        # "Raw" scenario: 30 samples, all helpful
        fb_raw     = category_feedback(total_w=30, helpful_w=30)
        # "Decayed" scenario: same proportions but heavily time-discounted (e.g. old data)
        fb_decayed = category_feedback(total_w=5, helpful_w=5)

        old = {"code_quality": 1.0}
        raw_weights,    _, _ = compute_weight_updates(fb_raw,     dict(old), cfg=cfg)
        decayed_weights, _, _ = compute_weight_updates(fb_decayed, dict(old), cfg=cfg)

        delta_raw     = abs(raw_weights["code_quality"]     - 1.0)
        delta_decayed = abs(decayed_weights["code_quality"] - 1.0)

        assert delta_raw > delta_decayed, (
            "Decayed (low total_w) should produce smaller update than raw (high total_w)"
        )


# ---------------------------------------------------------------------------
# Test 6 — Category fallback when metric has too few samples
# ---------------------------------------------------------------------------

class TestCategoryFallback:
    """Metric-level update must be skipped (and logged as such) when below min_feedback_samples."""

    def test_metric_skipped_below_minimum(self):
        cfg = make_cfg(min_feedback_samples=5)
        fb_cat    = category_feedback(total_w=10, helpful_w=8)
        fb_metric = metric_feedback("test_coverage", total_w=2, helpful_w=2)

        _, log, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            cfg=cfg,
        )
        metric_entries = [e for e in log if e.get("level") == "metric"]
        assert len(metric_entries) == 1
        assert metric_entries[0]["action"] == "skipped"

    def test_metric_updated_above_minimum(self):
        cfg = make_cfg(min_feedback_samples=3)
        fb_cat    = category_feedback(total_w=10, helpful_w=8)
        fb_metric = metric_feedback("test_coverage", total_w=10, helpful_w=9)

        _, log, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            cfg=cfg,
        )
        metric_entries = [e for e in log if e.get("level") == "metric" and e["action"] == "updated"]
        assert len(metric_entries) == 1
        assert "test_coverage" in new_metric_weights


# ---------------------------------------------------------------------------
# Test 7 — Convergence
# ---------------------------------------------------------------------------

class TestConvergence:
    """Repeated positive feedback cycles converge toward (not past) WEIGHT_MAX."""

    def test_weight_converges_near_max_after_many_cycles(self):
        cfg = make_cfg(
            min_feedback_samples=3,
            confidence_sample_target=30,
            self_learning_rate=0.08,
            weight_min=0.3,
            weight_max=2.0,
        )
        weights = {"code_quality": 1.0}
        fb = category_feedback(total_w=30, helpful_w=30, delta_w=10.0)

        for _ in range(100):
            new_weights, _, _ = compute_weight_updates(fb, weights, cfg=cfg)
            weights = new_weights

        # Should converge near WEIGHT_MAX but never exceed it
        assert weights["code_quality"] <= WEIGHT_MAX
        assert weights["code_quality"] >= 1.5, (
            f"After 100 fully-positive cycles expected weight ≥ 1.5, got {weights['code_quality']}"
        )

    def test_symmetric_convergence_both_directions(self):
        """Negative feedback should converge down; positive should converge up."""
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30,
                       self_learning_rate=0.08, weight_min=0.3, weight_max=2.0)
        fb_up   = category_feedback(total_w=30, helpful_w=30)
        fb_down = category_feedback(total_w=30, helpful_w=0)

        w_up = w_down = {"code_quality": 1.0}
        for _ in range(50):
            w_up,   _, _ = compute_weight_updates(fb_up,   dict(w_up),   cfg=cfg)
            w_down, _, _ = compute_weight_updates(fb_down, dict(w_down), cfg=cfg)

        assert w_up["code_quality"] > 1.0
        assert w_down["code_quality"] < 1.0


# ---------------------------------------------------------------------------
# Test 8 — Per-metric granularity divergence
# ---------------------------------------------------------------------------

class TestPerMetricGranularity:
    """Two metrics in the same category must be able to diverge independently."""

    def test_two_metrics_diverge(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10,
                       self_learning_rate=0.08)
        fb_cat = {"code_quality": {"total_w": 10, "helpful_w": 7, "outcome_delta_sum_w": 0.0}}
        fb_metric = {
            "test_coverage":  {"total_w": 10, "helpful_w": 10, "outcome_delta_sum_w": 0.0, "category": "code_quality"},
            "defect_density": {"total_w": 10, "helpful_w":  0, "outcome_delta_sum_w": 0.0, "category": "code_quality"},
        }

        _, _, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            current_metric_weights={},
            cfg=cfg,
        )

        cov_weight = new_metric_weights["test_coverage"]["weight"]
        def_weight = new_metric_weights["defect_density"]["weight"]

        assert cov_weight > 1.0, "test_coverage (100% helpful) weight should increase"
        assert def_weight < 1.0, "defect_density (0% helpful) weight should decrease"
        assert cov_weight > def_weight, "Metrics in same category should diverge"

    def test_confidence_differs_by_sample_count(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30)
        fb_cat = {"code_quality": {"total_w": 20, "helpful_w": 14, "outcome_delta_sum_w": 0.0}}
        fb_metric = {
            "test_coverage":  {"total_w": 30, "helpful_w": 20, "outcome_delta_sum_w": 0.0, "category": "code_quality"},
            "defect_density": {"total_w": 3,  "helpful_w": 2,  "outcome_delta_sum_w": 0.0, "category": "code_quality"},
        }

        _, _, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            cfg=cfg,
        )

        cov_conf = new_metric_weights["test_coverage"]["confidence"]
        def_conf = new_metric_weights["defect_density"]["confidence"]

        assert cov_conf > def_conf, (
            f"Higher-sample metric should have higher confidence "
            f"({cov_conf:.3f} vs {def_conf:.3f})"
        )

    def test_trend_field_populated(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10)
        fb_cat    = {"code_quality": {"total_w": 10, "helpful_w": 9, "outcome_delta_sum_w": 0.0}}
        fb_metric = {"test_coverage": {"total_w": 10, "helpful_w": 9, "outcome_delta_sum_w": 0.0, "category": "code_quality"}}

        _, _, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            cfg=cfg,
        )

        trend = new_metric_weights["test_coverage"]["trend"]
        assert trend in ("increasing", "decreasing", "stable"), f"Unexpected trend value: {trend}"
        assert trend == "increasing", "90% helpful should produce increasing trend"


# ---------------------------------------------------------------------------
# Test 9 — Minimum feedback threshold enforcement
# ---------------------------------------------------------------------------

class TestMinimumFeedbackThreshold:
    """Categories below min_feedback_samples must be skipped and logged."""

    def test_skip_logged_correctly(self):
        cfg = make_cfg(min_feedback_samples=5)
        fb  = category_feedback(total_w=3, helpful_w=3)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)

        skipped = [e for e in log if e["action"] == "skipped"]
        assert len(skipped) == 1
        assert skipped[0]["old_weight"] == 1.0
        assert skipped[0]["new_weight"] == 1.0
        assert new_weights["code_quality"] == 1.0, "Skipped weight must not change"

    def test_no_update_when_all_skipped(self):
        cfg = make_cfg(min_feedback_samples=100)
        fb  = {"a": {"total_w": 3, "helpful_w": 3, "outcome_delta_sum_w": 0.0},
               "b": {"total_w": 5, "helpful_w": 5, "outcome_delta_sum_w": 0.0}}
        old = {"a": 1.0, "b": 0.8}
        new_weights, log, _ = compute_weight_updates(fb, old, cfg=cfg)
        assert new_weights == old, "All-skipped run must return weights unchanged"


# ---------------------------------------------------------------------------
# Entry point (also runnable as python tests/test_self_learner.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestClampingBounds,
        TestDirectionCorrectness,
        TestConfidenceScaling,
        TestOutcomeBlending,
        TestRecencyDecayPassthrough,
        TestCategoryFallback,
        TestConvergence,
        TestPerMetricGranularity,
        TestMinimumFeedbackThreshold,
    ]

    passed = failed = 0
    for cls in test_classes:
        instance = cls()
        methods  = [m for m in dir(instance) if m.startswith("test_")]
        for method_name in methods:
            try:
                getattr(instance, method_name)()
                print(f"  PASS  {cls.__name__}.{method_name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}.{method_name}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
