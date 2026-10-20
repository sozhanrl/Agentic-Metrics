"""
refactoring_classifier.py
-------------------------
Dataset B & C Pipeline: OnlyTrivial_dt.csv & OnlyNonTrivial_dt.csv
Implements per dataset:
1. Random Forest Classifier (refactoring classification)
2. XGBoost Classifier
3. Logistic Regression (baseline)
4. Isolation Forest (anomalous code metric patterns)

Target: 'refactoring' (binary: 0 or 1)
Label Semantics: The 'refactoring' column indicates whether a record is
    associated with a refactoring operation (1) or not (0) in the dataset.
    This does NOT automatically mean refactoring *should* be performed;
    it reflects the dataset's observed label definition.

Splitting Strategy: Group-aware splitting by 'class' column to prevent
    data leakage from related records belonging to the same class.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, accuracy_score
)

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


TARGET_COLUMN = "refactoring"

# Columns excluded from features:
# - 'refactoring' (target)
# - 'file' (identifier, not predictive unless deliberately used)
# - 'class' (identifier, used for group splitting, not as a feature)
EXCLUDE_COLUMNS = {"refactoring", "file", "class"}

# 'type' column is categorical (class, innerclass, anonymous, interface, enum)
# and will be label-encoded
CATEGORICAL_COLUMNS = ["type"]

LABEL_NAMES = {
    0: "No refactoring association",
    1: "Refactoring-associated record",
}


class RefactoringClassifierPipeline:
    """
    End-to-end ML pipeline for refactoring classification.
    Supports both trivial and non-trivial datasets independently.
    """

    def __init__(self, artifacts_dir: str, dataset_label: str):
        """
        Args:
            artifacts_dir: directory to save model artifacts
            dataset_label: 'trivial' or 'nontrivial' to distinguish bundles
        """
        self.artifacts_dir = artifacts_dir
        self.dataset_label = dataset_label
        os.makedirs(self.artifacts_dir, exist_ok=True)

        self.scaler: Optional[StandardScaler] = None
        self.type_encoder: Optional[LabelEncoder] = None
        self.rf_classifier: Optional[RandomForestClassifier] = None
        self.xgb_classifier = None
        self.lr_classifier: Optional[LogisticRegression] = None
        self.isolation_forest: Optional[IsolationForest] = None
        self.feature_columns: List[str] = []
        self.evaluation_results: Dict[str, Any] = {}
        self.trained_at: Optional[str] = None
        self.dataset_info: Dict[str, Any] = {}

    @staticmethod
    def load_dataset(csv_path: str, sample_size: Optional[int] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads and validates the refactoring dataset.
        For large datasets (>500K rows), can optionally sample for faster training.
        Returns (dataframe, dataset_info_dict).
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Dataset not found: {csv_path}")

        df = pd.read_csv(csv_path)

        if TARGET_COLUMN not in df.columns:
            raise ValueError(f"Target column '{TARGET_COLUMN}' not found in dataset")

        info = {
            "path": csv_path,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": df.columns.tolist(),
            "target_distribution": df[TARGET_COLUMN].value_counts().to_dict(),
            "target_balance_ratio": round(
                float(df[TARGET_COLUMN].value_counts().min()) /
                float(df[TARGET_COLUMN].value_counts().max()), 4
            ),
            "label_semantics": LABEL_NAMES,
            "unique_files": int(df["file"].nunique()) if "file" in df.columns else 0,
            "unique_classes": int(df["class"].nunique()) if "class" in df.columns else 0,
            "unique_types": df["type"].value_counts().to_dict() if "type" in df.columns else {},
            "missing_values": {
                col: int(df[col].isnull().sum())
                for col in df.columns if df[col].isnull().sum() > 0
            },
        }

        # Stratified sampling if dataset is very large
        if sample_size and len(df) > sample_size:
            n_classes = max(df[TARGET_COLUMN].nunique(), 1)
            n_per_class = sample_size // n_classes
            parts = []
            for _, group in df.groupby(TARGET_COLUMN):
                parts.append(group.sample(n=min(len(group), n_per_class), random_state=42))
            df_sampled = pd.concat(parts, ignore_index=True)
            info["sampled_rows"] = len(df_sampled)
            info["sampling_strategy"] = f"Stratified sample of {len(df_sampled)} from {len(df)}"
            return df_sampled, info

        return df, info

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        """
        Prepare feature matrix:
        1. Drop excluded columns (target, file, class)
        2. Encode 'type' categorically
        3. Fill missing values
        4. Scale features
        """
        # Determine numeric feature columns
        all_cols = df.columns.tolist()
        feature_cols = [c for c in all_cols if c not in EXCLUDE_COLUMNS]

        # Separate numeric and categorical
        numeric_cols = [c for c in feature_cols if c not in CATEGORICAL_COLUMNS and c in df.select_dtypes(include=[np.number]).columns]
        cat_cols = [c for c in feature_cols if c in CATEGORICAL_COLUMNS and c in df.columns]

        X_parts = []

        # Numeric features
        X_numeric = df[numeric_cols].fillna(0).values
        X_parts.append(X_numeric)

        if fit:
            self.feature_columns = numeric_cols.copy()

        # Categorical encoding for 'type'
        if "type" in cat_cols:
            if fit:
                self.type_encoder = LabelEncoder()
                type_encoded = self.type_encoder.fit_transform(df["type"].fillna("unknown").astype(str))
            else:
                # Handle unseen categories
                known = set(self.type_encoder.classes_)
                type_vals = df["type"].fillna("unknown").astype(str)
                type_vals = type_vals.apply(lambda x: x if x in known else "unknown")
                if "unknown" not in known:
                    self.type_encoder.classes_ = np.append(self.type_encoder.classes_, "unknown")
                type_encoded = self.type_encoder.transform(type_vals)

            X_parts.append(type_encoded.reshape(-1, 1))
            if fit:
                self.feature_columns.append("type_encoded")

        X_raw = np.hstack(X_parts)

        if fit:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X_raw)
        else:
            X_scaled = self.scaler.transform(X_raw)

        return X_scaled

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains RF, XGBoost, Logistic Regression, Isolation Forest.
        Uses group-aware splitting by 'class' to prevent data leakage.
        """
        y = df[TARGET_COLUMN].values.astype(int)
        X_scaled = self._prepare_features(df, fit=True)

        # Group-aware splitting by 'class' column
        if "class" in df.columns:
            groups = df["class"].values
            gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
            train_idx, test_idx = next(gss.split(X_scaled, y, groups=groups))
            splitting_strategy = "Group-aware split by 'class' (80/20), preventing related records leaking across partitions"
        else:
            # Fallback: simple stratified split
            from sklearn.model_selection import train_test_split
            indices = np.arange(len(X_scaled))
            train_idx, test_idx = train_test_split(indices, test_size=0.2, stratify=y, random_state=42)
            splitting_strategy = "Stratified random split (80/20)"

        X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        results = {}

        # ================================================================
        # 1. Random Forest Classifier
        # ================================================================
        self.rf_classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self.rf_classifier.fit(X_train, y_train)
        rf_probs = self.rf_classifier.predict_proba(X_test)[:, 1]
        rf_preds = (rf_probs >= 0.5).astype(int)
        results["random_forest"] = self._compute_metrics(y_test, rf_preds, rf_probs)
        results["random_forest"]["feature_importances"] = dict(
            zip(self.feature_columns, [round(float(v), 4) for v in self.rf_classifier.feature_importances_])
        )

        # ================================================================
        # 2. XGBoost Classifier
        # ================================================================
        if HAS_XGBOOST:
            n_neg = int((y_train == 0).sum())
            n_pos = int((y_train == 1).sum())
            scale_pos_weight = n_neg / max(n_pos, 1)

            self.xgb_classifier = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.08,
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                eval_metric="logloss",
                verbosity=0,
                use_label_encoder=False,
                n_jobs=-1,
            )
            self.xgb_classifier.fit(X_train, y_train)
            xgb_probs = self.xgb_classifier.predict_proba(X_test)[:, 1]
            xgb_preds = (xgb_probs >= 0.5).astype(int)
            results["xgboost"] = self._compute_metrics(y_test, xgb_preds, xgb_probs)
            results["xgboost"]["feature_importances"] = dict(
                zip(self.feature_columns, [round(float(v), 4) for v in self.xgb_classifier.feature_importances_])
            )
        else:
            results["xgboost"] = {"status": "unavailable", "reason": "xgboost not installed"}

        # ================================================================
        # 3. Logistic Regression (baseline)
        # ================================================================
        self.lr_classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
            solver="lbfgs",
        )
        self.lr_classifier.fit(X_train, y_train)
        lr_probs = self.lr_classifier.predict_proba(X_test)[:, 1]
        lr_preds = (lr_probs >= 0.5).astype(int)
        results["logistic_regression"] = self._compute_metrics(y_test, lr_preds, lr_probs)
        coef_importance = np.abs(self.lr_classifier.coef_[0])
        coef_importance = coef_importance / max(coef_importance.sum(), 1e-10)
        results["logistic_regression"]["feature_importances"] = dict(
            zip(self.feature_columns, [round(float(v), 4) for v in coef_importance])
        )

        # ================================================================
        # 4. Isolation Forest (unsupervised anomaly detection)
        # ================================================================
        self.isolation_forest = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=200,
        )
        self.isolation_forest.fit(X_train)
        anomaly_preds = self.isolation_forest.predict(X_test)
        n_anomalies = int((anomaly_preds == -1).sum())
        results["isolation_forest"] = {
            "test_samples": len(X_test),
            "anomalies_detected": n_anomalies,
            "anomaly_rate": round(n_anomalies / max(len(X_test), 1), 4),
            "contamination": 0.05,
        }

        # Champion model selection
        model_scores = {}
        for name in ["random_forest", "xgboost", "logistic_regression"]:
            if "f1" in results.get(name, {}):
                model_scores[name] = results[name]["f1"]
        champion = max(model_scores, key=model_scores.get) if model_scores else "random_forest"
        results["champion_model"] = champion
        results["champion_f1"] = model_scores.get(champion, 0.0)

        # Dataset metadata
        results["dataset"] = {
            "name": f"Only{'Trivial' if self.dataset_label == 'trivial' else 'NonTrivial'}_dt.csv",
            "label": self.dataset_label,
            "total_samples": len(df),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "features": self.feature_columns,
            "target": TARGET_COLUMN,
            "label_semantics": LABEL_NAMES,
            "class_distribution": {
                str(k): int(v) for k, v in pd.Series(y).value_counts().items()
            },
            "splitting_strategy": splitting_strategy,
            "class_imbalance_handling": "class_weight='balanced' / scale_pos_weight",
            "group_column": "class" if "class" in df.columns else "none",
        }

        self.evaluation_results = results
        self.trained_at = datetime.now(timezone.utc).isoformat()
        self._save_bundle()

        return results

    def _compute_metrics(self, y_true, y_pred, y_prob) -> Dict[str, Any]:
        """Computes classification metrics."""
        return {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
            "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
            "support": {
                "class_0": int((y_true == 0).sum()),
                "class_1": int((y_true == 1).sum()),
            },
        }

    def _save_bundle(self):
        """Saves trained model bundle to disk."""
        bundle_path = os.path.join(
            self.artifacts_dir,
            f"refactoring_{self.dataset_label}_bundle.joblib"
        )
        joblib.dump({
            "scaler": self.scaler,
            "type_encoder": self.type_encoder,
            "rf_classifier": self.rf_classifier,
            "xgb_classifier": self.xgb_classifier,
            "lr_classifier": self.lr_classifier,
            "isolation_forest": self.isolation_forest,
            "feature_columns": self.feature_columns,
            "evaluation_results": self.evaluation_results,
            "trained_at": self.trained_at,
            "dataset_label": self.dataset_label,
        }, bundle_path)

    def load_bundle(self) -> bool:
        """Loads previously trained models from disk."""
        bundle_path = os.path.join(
            self.artifacts_dir,
            f"refactoring_{self.dataset_label}_bundle.joblib"
        )
        if not os.path.exists(bundle_path):
            return False
        try:
            bundle = joblib.load(bundle_path)
            self.scaler = bundle["scaler"]
            self.type_encoder = bundle.get("type_encoder")
            self.rf_classifier = bundle["rf_classifier"]
            self.xgb_classifier = bundle.get("xgb_classifier")
            self.lr_classifier = bundle.get("lr_classifier")
            self.isolation_forest = bundle.get("isolation_forest")
            self.feature_columns = bundle.get("feature_columns", [])
            self.evaluation_results = bundle.get("evaluation_results", {})
            self.trained_at = bundle.get("trained_at")
            return True
        except Exception:
            return False

    def predict(self, features: Dict[str, float], model_name: str = "auto") -> Dict[str, Any]:
        """
        Predicts refactoring classification for a single component.
        """
        if self.scaler is None:
            if not self.load_bundle():
                return {"error": f"Refactoring classifier ({self.dataset_label}) not trained."}

        # Build feature vector
        input_data = {}
        for col in self.feature_columns:
            if col == "type_encoded":
                continue
            input_data[col] = features.get(col, 0.0)

        input_df = pd.DataFrame([input_data])
        # Add type column for encoding
        if self.type_encoder is not None:
            input_df["type"] = features.get("type", "class")

        X_scaled = self._prepare_features(input_df, fit=False)

        # Select model
        if model_name == "auto":
            model_name = self.evaluation_results.get("champion_model", "random_forest")

        if model_name == "xgboost" and self.xgb_classifier is not None:
            prob = float(self.xgb_classifier.predict_proba(X_scaled)[0, 1])
            importances = self.evaluation_results.get("xgboost", {}).get("feature_importances", {})
        elif model_name == "logistic_regression" and self.lr_classifier is not None:
            prob = float(self.lr_classifier.predict_proba(X_scaled)[0, 1])
            importances = self.evaluation_results.get("logistic_regression", {}).get("feature_importances", {})
        else:
            model_name = "random_forest"
            prob = float(self.rf_classifier.predict_proba(X_scaled)[0, 1])
            importances = self.evaluation_results.get("random_forest", {}).get("feature_importances", {})

        pred = int(prob >= 0.5)

        # Anomaly check
        anom_score = float(self.isolation_forest.decision_function(X_scaled)[0])
        is_anomaly = bool(self.isolation_forest.predict(X_scaled)[0] == -1)

        # Top factors
        sorted_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        top_factors = sorted_importances[:5]

        return {
            "prediction": pred,
            "prediction_label": LABEL_NAMES.get(pred, "Unknown"),
            "probability": round(prob, 4),
            "refactoring_probability": round(prob, 4),
            "model_used": model_name,
            "dataset_type": self.dataset_label,
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anom_score, 4),
            "top_contributing_factors": dict(top_factors),
            "label_semantics": LABEL_NAMES,
            "note": (
                "The 'refactoring' label reflects the dataset's observed classification. "
                "It does not automatically indicate that refactoring should be performed."
            ),
            "trained_at": self.trained_at,
        }


def compare_trivial_vs_nontrivial(
    trivial_results: Dict[str, Any],
    nontrivial_results: Dict[str, Any],
    overlap_info: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Builds a comparison report between trivial and nontrivial refactoring datasets.
    """
    comparison = {
        "datasets": {
            "trivial": {
                "name": "OnlyTrivial_dt.csv",
                "total_samples": trivial_results.get("dataset", {}).get("total_samples", 0),
                "train_samples": trivial_results.get("dataset", {}).get("train_samples", 0),
                "test_samples": trivial_results.get("dataset", {}).get("test_samples", 0),
                "champion_model": trivial_results.get("champion_model", "N/A"),
                "champion_f1": trivial_results.get("champion_f1", 0.0),
                "splitting_strategy": trivial_results.get("dataset", {}).get("splitting_strategy", "N/A"),
            },
            "nontrivial": {
                "name": "OnlyNonTrivial_dt.csv",
                "total_samples": nontrivial_results.get("dataset", {}).get("total_samples", 0),
                "train_samples": nontrivial_results.get("dataset", {}).get("train_samples", 0),
                "test_samples": nontrivial_results.get("dataset", {}).get("test_samples", 0),
                "champion_model": nontrivial_results.get("champion_model", "N/A"),
                "champion_f1": nontrivial_results.get("champion_f1", 0.0),
                "splitting_strategy": nontrivial_results.get("dataset", {}).get("splitting_strategy", "N/A"),
            },
        },
        "model_comparison": {},
        "feature_importance_comparison": {},
    }

    # Per-model comparison
    for model_name in ["random_forest", "xgboost", "logistic_regression"]:
        triv = trivial_results.get(model_name, {})
        nontriv = nontrivial_results.get(model_name, {})
        if "f1" in triv and "f1" in nontriv:
            comparison["model_comparison"][model_name] = {
                "trivial": {
                    "accuracy": triv.get("accuracy", 0),
                    "precision": triv.get("precision", 0),
                    "recall": triv.get("recall", 0),
                    "f1": triv.get("f1", 0),
                    "roc_auc": triv.get("roc_auc", 0),
                },
                "nontrivial": {
                    "accuracy": nontriv.get("accuracy", 0),
                    "precision": nontriv.get("precision", 0),
                    "recall": nontriv.get("recall", 0),
                    "f1": nontriv.get("f1", 0),
                    "roc_auc": nontriv.get("roc_auc", 0),
                },
                "f1_difference": round(triv.get("f1", 0) - nontriv.get("f1", 0), 4),
            }

    # Feature importance comparison (using champion models)
    for dataset_label, results in [("trivial", trivial_results), ("nontrivial", nontrivial_results)]:
        champion = results.get("champion_model", "random_forest")
        importances = results.get(champion, {}).get("feature_importances", {})
        top_5 = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
        comparison["feature_importance_comparison"][dataset_label] = {
            "champion_model": champion,
            "top_5_features": dict(top_5),
        }

    # Overlap info
    if overlap_info:
        comparison["overlap_analysis"] = overlap_info
    else:
        comparison["overlap_analysis"] = {
            "overlapping_files": 0,
            "overlapping_classes": "Not computed",
            "note": "Datasets represent different populations; separate evaluation preserved.",
        }

    # Limitations
    comparison["limitations"] = [
        "A higher F1 score on one dataset does not prove one refactoring approach is better without domain evidence.",
        "The 'refactoring' label semantics may differ between trivial and non-trivial contexts.",
        "Class overlap (15,064 shared classes) means some code components appear in both datasets; separate models are maintained.",
        "Group-aware splitting by 'class' mitigates but does not eliminate all possible leakage.",
    ]

    return comparison
