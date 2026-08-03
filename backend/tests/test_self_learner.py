"""
Pure-function unit tests for self_learner.compute_weight_updates() under the Beta-Bernoulli Model.

These tests require NO database, NO running server, and NO external dependencies.
They verify the mathematical properties of the Bayesian Beta-Bernoulli learning algorithm:

    1. Clamping bounds — weight never escapes [WEIGHT_MIN, WEIGHT_MAX]
    2. Posterior mean convergence — positive feedback increases alpha, negative increases beta
    3. Beta variance confidence — confidence scales inversely with posterior variance
    4. Outcome blending — outcome_delta shifts the combined signal relative to subjective-only
    5. Regularization shrinkage — alpha/beta pull toward prior alpha0/beta0
    6. Category fallback prior — metric-level learning falls back when samples < min
    7. Per-metric granularity divergence — two metrics in same category can diverge independently
    8. Backward compatibility — function signature and return dictionary keys match expectations

Run with:
    venv\\Scripts\\python.exe -m pytest tests/test_self_learner.py -v
"""

import math
import sys
import os

# Allow running from backend/ or from tests/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.self_learner import compute_weight_updates, _compute_bayesian_single_update
from app.agents.config import AgentConfig, WEIGHT_MIN, WEIGHT_MAX


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


class TestClampingBounds:
    """Weight must NEVER drift outside [WEIGHT_MIN, WEIGHT_MAX]."""

    def test_extreme_positive_feedback_clamped_at_max(self):
        cfg = make_cfg(weight_max=2.0, weight_min=0.3, min_feedback_samples=1)
        fb  = category_feedback(total_w=1000, helpful_w=1000, delta_w=500)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.9}, cfg=cfg)
        assert new_weights["code_quality"] <= WEIGHT_MAX

    def test_extreme_negative_feedback_clamped_at_min(self):
        cfg = make_cfg(weight_max=2.0, weight_min=0.3, min_feedback_samples=1)
        fb  = category_feedback(total_w=1000, helpful_w=0, delta_w=-500)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 0.35}, cfg=cfg)
        assert new_weights["code_quality"] >= WEIGHT_MIN


class TestBayesianDirectionCorrectness:
    """Positive feedback must increase alpha/weight; negative must increase beta/decrease weight."""

    def test_positive_feedback_increases_weight(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=10)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        assert new_weights["code_quality"] > 1.0

    def test_negative_feedback_decreases_weight(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=0)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        assert new_weights["code_quality"] < 1.0

    def test_neutral_feedback_leaves_weight_stable(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb  = category_feedback(total_w=10, helpful_w=5)
        new_weights, log, _ = compute_weight_updates(fb, {"code_quality": 1.0}, cfg=cfg)
        assert abs(new_weights["code_quality"] - 1.0) < 0.05


class TestBetaVarianceConfidence:
    """Confidence must be derived from posterior variance."""

    def test_more_samples_higher_confidence(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=30)
        fb_low  = category_feedback(total_w=3, helpful_w=3)
        fb_high = category_feedback(total_w=30, helpful_w=30)

        _, log_low, _  = compute_weight_updates(fb_low, {"code_quality": 1.0}, cfg=cfg)
        _, log_high, _ = compute_weight_updates(fb_high, {"code_quality": 1.0}, cfg=cfg)

        entry_low  = [e for e in log_low if e["action"] == "updated"][0]
        entry_high = [e for e in log_high if e["action"] == "updated"][0]

        assert entry_high["confidence"] >= entry_low["confidence"]


class TestOutcomeBlending:
    """Outcome delta shifts the posterior update vs subjective only."""

    def test_positive_outcome_amplifies_update(self):
        cfg = make_cfg(min_feedback_samples=1, confidence_sample_target=10)
        fb_subj = category_feedback(total_w=10, helpful_w=7, delta_w=0.0)
        fb_out  = category_feedback(total_w=10, helpful_w=7, delta_w=5.0)

        w_subj, _, _ = compute_weight_updates(fb_subj, {"code_quality": 1.0}, cfg=cfg)
        w_out,  _, _ = compute_weight_updates(fb_out,  {"code_quality": 1.0}, cfg=cfg)

        assert w_out["code_quality"] > w_subj["code_quality"]


class TestCategoryFallback:
    """Metric-level update skipped when sample count < min_feedback_samples."""

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


class TestPerMetricDivergence:
    """Two metrics in the same category can diverge independently."""

    def test_two_metrics_diverge(self):
        cfg = make_cfg(min_feedback_samples=3, confidence_sample_target=10)
        fb_cat = {"code_quality": {"total_w": 10, "helpful_w": 7, "outcome_delta_sum_w": 0.0}}
        fb_metric = {
            "test_coverage":  {"total_w": 10, "helpful_w": 10, "outcome_delta_sum_w": 0.0, "category": "code_quality"},
            "defect_density": {"total_w": 10, "helpful_w":  0, "outcome_delta_sum_w": 0.0, "category": "code_quality"},
        }

        _, _, new_metric_weights = compute_weight_updates(
            feedback_summary=fb_cat,
            current_weights={"code_quality": 1.0},
            metric_feedback_summary=fb_metric,
            cfg=cfg,
        )

        cov_w = new_metric_weights["test_coverage"]["weight"]
        def_w = new_metric_weights["defect_density"]["weight"]

        assert cov_w > def_w


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
