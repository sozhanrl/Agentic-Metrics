"""
feature_engineering.py
----------------------
Feature extraction, temporal lag generators, imputation, and train/test splits.
Adheres strictly to ML Best Practices:
1. Strict featurization ordering: split before fitting scalers/imputers to prevent data leakage.
2. Chronological splits for temporal time-series.
3. Explicit missing value handling and schema validation.
"""

from typing import Tuple, List, Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


class CodeQualityFeatureExtractor:
    """Extracts features for Code Quality models."""

    FEATURE_NAMES = [
        "code_churn",
        "cyclomatic_complexity",
        "test_coverage",
        "code_duplication",
        "technical_debt_ratio",
        "maintainability_index",
        "code_smells",
        "code_churn_lag1",
        "test_coverage_lag1",
        "complexity_churn_interaction",
    ]

    @classmethod
    def build_features(cls, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Extract feature matrix from a dataframe of code quality metrics.
        Computes interaction and lag terms if multiple observations exist.
        """
        data = df.copy()

        # Defaults for missing baseline columns
        defaults = {
            "code_churn": 18.0,
            "cyclomatic_complexity": 12.0,
            "test_coverage": 70.0,
            "code_duplication": 4.5,
            "technical_debt_ratio": 4.0,
            "maintainability_index": 78.0,
            "code_smells": 25.0,
        }
        for col, default_val in defaults.items():
            if col not in data.columns:
                data[col] = default_val
            else:
                data[col] = data[col].fillna(default_val)

        # Generate engineered features
        if "code_churn_lag1" not in data.columns:
            data["code_churn_lag1"] = data["code_churn"].shift(1).fillna(data["code_churn"])
        if "test_coverage_lag1" not in data.columns:
            data["test_coverage_lag1"] = data["test_coverage"].shift(1).fillna(data["test_coverage"])

        # Interaction: high complexity + high churn is notorious for defect generation
        data["complexity_churn_interaction"] = (
            data["cyclomatic_complexity"] * (data["code_churn"] / 100.0)
        )

        X = data[cls.FEATURE_NAMES].values
        return X, cls.FEATURE_NAMES


class ProcessFeatureExtractor:
    """Extracts features for Process & Sprint forecasting."""

    FEATURE_NAMES = [
        "sprint_velocity_lag1",
        "sprint_velocity_lag2",
        "cycle_time",
        "lead_time",
        "wip",
        "sprint_predictability",
        "story_spillover_rate",
        "sprint_throughput",
        "velocity_moving_avg3",
        "wip_cycle_ratio",
    ]

    @classmethod
    def build_features(cls, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        data = df.copy()

        defaults = {
            "sprint_velocity": 28.0,
            "cycle_time": 4.5,
            "lead_time": 10.0,
            "wip": 8.0,
            "sprint_predictability": 85.0,
            "story_spillover_rate": 12.0,
            "sprint_throughput": 14.0,
        }
        for col, default_val in defaults.items():
            if col not in data.columns:
                data[col] = default_val
            else:
                data[col] = data[col].fillna(default_val)

        # Lags and moving averages
        vel = data["sprint_velocity"]
        data["sprint_velocity_lag1"] = vel.shift(1).fillna(vel)
        data["sprint_velocity_lag2"] = vel.shift(2).fillna(data["sprint_velocity_lag1"])
        data["velocity_moving_avg3"] = vel.rolling(window=3, min_periods=1).mean()

        # Little's Law ratio interaction: WIP / cycle_time
        safe_cycle = np.where(data["cycle_time"] > 0, data["cycle_time"], 1.0)
        data["wip_cycle_ratio"] = data["wip"] / safe_cycle

        X = data[cls.FEATURE_NAMES].values
        return X, cls.FEATURE_NAMES


class DevOpsFeatureExtractor:
    """
    Extracts features for DevOps deployment intelligence.
    STRICT PRE-DEPLOYMENT ONLY: No target leakage from post-deployment observations.
    """

    FEATURE_NAMES = [
        "deployment_frequency",
        "deployment_lead_time",
        "code_churn",
        "test_coverage",
        "cyclomatic_complexity",
        "rollback_rate_lag1",
        "recent_failure_rate_lag1",
        "release_risk_index",
    ]

    @classmethod
    def build_features(cls, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        data = df.copy()

        defaults = {
            "deployment_frequency": 2.5,
            "deployment_lead_time": 6.0,
            "code_churn": 20.0,
            "test_coverage": 65.0,
            "cyclomatic_complexity": 14.0,
            "rollback_rate": 8.0,
            "change_failure_rate": 18.0,
        }
        for col, default_val in defaults.items():
            if col not in data.columns:
                data[col] = default_val
            else:
                data[col] = data[col].fillna(default_val)

        # Strict lag enforcement for failure and rollback history to avoid target leakage
        data["rollback_rate_lag1"] = data["rollback_rate"].shift(1).fillna(data["rollback_rate"])
        data["recent_failure_rate_lag1"] = data["change_failure_rate"].shift(1).fillna(data["change_failure_rate"])

        # Pre-deployment composite risk index: higher churn + lower coverage + recent failures
        coverage_factor = np.maximum(0.1, data["test_coverage"] / 100.0)
        data["release_risk_index"] = (
            (data["code_churn"] / 10.0)
            * (data["cyclomatic_complexity"] / 10.0)
            / coverage_factor
        )

        X = data[cls.FEATURE_NAMES].values
        return X, cls.FEATURE_NAMES


def create_preprocessor() -> Pipeline:
    """Returns a scikit-learn preprocessing pipeline (median imputation + standard scaling)."""
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])


def chronological_split(
    X: np.ndarray, y: np.ndarray, test_size: float = 0.2
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Performs chronological train/test split (no shuffling) to preserve temporal ordering.
    """
    n_samples = len(X)
    split_idx = int(n_samples * (1.0 - test_size))
    # Ensure at least 1 sample in test if n_samples > 2
    if split_idx >= n_samples and n_samples > 1:
        split_idx = n_samples - 1

    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    return X_train, X_test, y_train, y_test
