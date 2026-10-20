"""
defect_classifier.py
--------------------
Dataset A Pipeline: SoftwareDefectDataset.csv
Implements:
1. Random Forest Classifier (defect-prone classification)
2. XGBoost Classifier (nonlinear defect classification)
3. Logistic Regression (baseline)
4. Isolation Forest (unsupervised anomaly detection)

Target: DEFECT_LABEL (binary: 0=non-defective, 1=defective)
Features: LOC, CYCLO, LENGTH, VOLUME, DIFFICULTY, INT_FAN_IN, INT_FAN_OUT,
          NUM_OPERATORS, NUM_OPERANDS, BRANCH_COUNT
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, classification_report, accuracy_score
)
from sklearn.pipeline import Pipeline

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


FEATURE_COLUMNS = [
    "LOC", "CYCLO", "LENGTH", "VOLUME", "DIFFICULTY",
    "INT_FAN_IN", "INT_FAN_OUT", "NUM_OPERATORS", "NUM_OPERANDS", "BRANCH_COUNT"
]
TARGET_COLUMN = "DEFECT_LABEL"

# Verified label semantics from dataset documentation:
# 0 = Non-defective component
# 1 = Defect-prone component
LABEL_NAMES = {0: "Non-Defective", 1: "Defect-Prone"}


class DefectClassifierPipeline:
    """
    End-to-end ML pipeline for software defect prediction
    using SoftwareDefectDataset.csv.
    """

    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = artifacts_dir
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self.scaler: Optional[StandardScaler] = None
        self.rf_classifier: Optional[RandomForestClassifier] = None
        self.xgb_classifier = None
        self.lr_classifier: Optional[LogisticRegression] = None
        self.calibrated_rf: Optional[CalibratedClassifierCV] = None
        self.isolation_forest: Optional[IsolationForest] = None
        self.evaluation_results: Dict[str, Any] = {}
        self.trained_at: Optional[str] = None
        self.dataset_info: Dict[str, Any] = {}

    @staticmethod
    def load_dataset(csv_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads and validates SoftwareDefectDataset.csv.
        Returns (dataframe, dataset_info_dict).
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Dataset not found: {csv_path}")

        df = pd.read_csv(csv_path)

        # Validate required columns
        missing_cols = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Dataset info
        info = {
            "path": csv_path,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": df.columns.tolist(),
            "missing_values": df.isnull().sum().to_dict(),
            "target_distribution": df[TARGET_COLUMN].value_counts().to_dict(),
            "target_balance_ratio": round(
                float(df[TARGET_COLUMN].value_counts().min()) /
                float(df[TARGET_COLUMN].value_counts().max()), 4
            ),
            "label_semantics": LABEL_NAMES,
            "feature_stats": {},
        }
        for col in FEATURE_COLUMNS:
            info["feature_stats"][col] = {
                "mean": round(float(df[col].mean()), 4),
                "std": round(float(df[col].std()), 4),
                "min": round(float(df[col].min()), 4),
                "max": round(float(df[col].max()), 4),
                "missing": int(df[col].isnull().sum()),
            }

        return df, info

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains RF, XGBoost, Logistic Regression, and Isolation Forest.
        Uses stratified k-fold cross-validation (k=5) for evaluation.
        SMOTE/resampling is NOT applied before the train/test split.
        """
        X = df[FEATURE_COLUMNS].copy()
        y = df[TARGET_COLUMN].copy()

        # Handle any missing values (none expected but defensive)
        X = X.fillna(X.median())
        y = y.fillna(0).astype(int)

        # Fit scaler on full training data
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Stratified 5-fold cross-validation
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        results = {}

        # ================================================================
        # 1. Random Forest Classifier (with class_weight='balanced')
        # ================================================================
        self.rf_classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_split=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        rf_probs = cross_val_predict(
            self.rf_classifier, X_scaled, y, cv=skf, method="predict_proba"
        )
        rf_preds = (rf_probs[:, 1] >= 0.5).astype(int)
        self.rf_classifier.fit(X_scaled, y)

        results["random_forest"] = self._compute_metrics(y, rf_preds, rf_probs[:, 1])
        results["random_forest"]["feature_importances"] = dict(
            zip(FEATURE_COLUMNS, [round(float(v), 4) for v in self.rf_classifier.feature_importances_])
        )

        # Calibrated RF for probability display
        self.calibrated_rf = CalibratedClassifierCV(
            self.rf_classifier, cv=3, method="isotonic"
        )
        self.calibrated_rf.fit(X_scaled, y)

        # ================================================================
        # 2. XGBoost Classifier
        # ================================================================
        if HAS_XGBOOST:
            # Compute scale_pos_weight for imbalance
            n_neg = int((y == 0).sum())
            n_pos = int((y == 1).sum())
            scale_pos_weight = n_neg / max(n_pos, 1)

            self.xgb_classifier = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.08,
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                eval_metric="logloss",
                verbosity=0,
                use_label_encoder=False,
            )
            xgb_probs = cross_val_predict(
                self.xgb_classifier, X_scaled, y, cv=skf, method="predict_proba"
            )
            xgb_preds = (xgb_probs[:, 1] >= 0.5).astype(int)
            self.xgb_classifier.fit(X_scaled, y)

            results["xgboost"] = self._compute_metrics(y, xgb_preds, xgb_probs[:, 1])
            results["xgboost"]["feature_importances"] = dict(
                zip(FEATURE_COLUMNS, [round(float(v), 4) for v in self.xgb_classifier.feature_importances_])
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
        lr_probs = cross_val_predict(
            self.lr_classifier, X_scaled, y, cv=skf, method="predict_proba"
        )
        lr_preds = (lr_probs[:, 1] >= 0.5).astype(int)
        self.lr_classifier.fit(X_scaled, y)

        results["logistic_regression"] = self._compute_metrics(y, lr_preds, lr_probs[:, 1])
        # Coefficient-based importances for LR
        coef_importance = np.abs(self.lr_classifier.coef_[0])
        coef_importance = coef_importance / coef_importance.sum()
        results["logistic_regression"]["feature_importances"] = dict(
            zip(FEATURE_COLUMNS, [round(float(v), 4) for v in coef_importance])
        )

        # ================================================================
        # 4. Isolation Forest (unsupervised anomaly detection)
        # ================================================================
        self.isolation_forest = IsolationForest(
            contamination=0.08,
            random_state=42,
            n_estimators=200,
        )
        self.isolation_forest.fit(X_scaled)
        anomaly_preds = self.isolation_forest.predict(X_scaled)
        anomaly_scores = self.isolation_forest.decision_function(X_scaled)
        n_anomalies = int((anomaly_preds == -1).sum())
        results["isolation_forest"] = {
            "total_samples": len(X_scaled),
            "anomalies_detected": n_anomalies,
            "anomaly_rate": round(n_anomalies / len(X_scaled), 4),
            "contamination": 0.08,
            "mean_anomaly_score": round(float(anomaly_scores.mean()), 4),
        }

        # ================================================================
        # Select champion model
        # ================================================================
        model_scores = {}
        for name in ["random_forest", "xgboost", "logistic_regression"]:
            if "f1" in results.get(name, {}):
                model_scores[name] = results[name]["f1"]

        champion = max(model_scores, key=model_scores.get) if model_scores else "random_forest"
        results["champion_model"] = champion
        results["champion_f1"] = model_scores.get(champion, 0.0)

        # Dataset metadata
        results["dataset"] = {
            "name": "SoftwareDefectDataset.csv",
            "total_samples": len(df),
            "features": FEATURE_COLUMNS,
            "target": TARGET_COLUMN,
            "label_semantics": LABEL_NAMES,
            "class_distribution": {
                str(k): int(v) for k, v in df[TARGET_COLUMN].value_counts().items()
            },
            "splitting_strategy": "Stratified 5-Fold Cross-Validation",
            "class_imbalance_handling": "class_weight='balanced' / scale_pos_weight",
        }

        self.evaluation_results = results
        self.trained_at = datetime.now(timezone.utc).isoformat()

        # Persist bundle
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
                "non_defective": int((y_true == 0).sum()),
                "defective": int((y_true == 1).sum()),
            },
        }

    def _save_bundle(self):
        """Saves all trained models and metadata."""
        bundle_path = os.path.join(self.artifacts_dir, "defect_classifier_bundle.joblib")
        joblib.dump({
            "scaler": self.scaler,
            "rf_classifier": self.rf_classifier,
            "calibrated_rf": self.calibrated_rf,
            "xgb_classifier": self.xgb_classifier,
            "lr_classifier": self.lr_classifier,
            "isolation_forest": self.isolation_forest,
            "evaluation_results": self.evaluation_results,
            "trained_at": self.trained_at,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "label_names": LABEL_NAMES,
        }, bundle_path)

    def load_bundle(self) -> bool:
        """Loads previously trained models from disk."""
        bundle_path = os.path.join(self.artifacts_dir, "defect_classifier_bundle.joblib")
        if not os.path.exists(bundle_path):
            return False
        try:
            bundle = joblib.load(bundle_path)
            self.scaler = bundle["scaler"]
            self.rf_classifier = bundle["rf_classifier"]
            self.calibrated_rf = bundle.get("calibrated_rf")
            self.xgb_classifier = bundle.get("xgb_classifier")
            self.lr_classifier = bundle.get("lr_classifier")
            self.isolation_forest = bundle.get("isolation_forest")
            self.evaluation_results = bundle.get("evaluation_results", {})
            self.trained_at = bundle.get("trained_at")
            return True
        except Exception:
            return False

    def predict(self, features: Dict[str, float], model_name: str = "auto") -> Dict[str, Any]:
        """
        Predicts defect risk for a single component given its metric features.
        Returns prediction, calibrated probability, risk category, and explainability.
        """
        if self.scaler is None:
            if not self.load_bundle():
                return {"error": "Defect classifier not trained. Train first via /api/ml/dataset/train."}

        # Validate input features
        input_df = pd.DataFrame([{col: features.get(col, 0.0) for col in FEATURE_COLUMNS}])
        X_scaled = self.scaler.transform(input_df)

        # Select model
        if model_name == "auto":
            model_name = self.evaluation_results.get("champion_model", "random_forest")

        # Get prediction and probability
        if model_name == "xgboost" and self.xgb_classifier is not None:
            model = self.xgb_classifier
            prob = float(model.predict_proba(X_scaled)[0, 1])
            pred = int(prob >= 0.5)
            importances = self.evaluation_results.get("xgboost", {}).get("feature_importances", {})
        elif model_name == "logistic_regression" and self.lr_classifier is not None:
            model = self.lr_classifier
            prob = float(model.predict_proba(X_scaled)[0, 1])
            pred = int(prob >= 0.5)
            importances = self.evaluation_results.get("logistic_regression", {}).get("feature_importances", {})
        else:
            model_name = "random_forest"
            # Use calibrated RF for probability
            if self.calibrated_rf is not None:
                prob = float(self.calibrated_rf.predict_proba(X_scaled)[0, 1])
            else:
                prob = float(self.rf_classifier.predict_proba(X_scaled)[0, 1])
            pred = int(prob >= 0.5)
            importances = self.evaluation_results.get("random_forest", {}).get("feature_importances", {})

        # Risk categorization
        if prob >= 0.75:
            risk_category = "CRITICAL"
        elif prob >= 0.5:
            risk_category = "HIGH"
        elif prob >= 0.3:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"

        # Anomaly detection
        anom_score = float(self.isolation_forest.decision_function(X_scaled)[0])
        is_anomaly = bool(self.isolation_forest.predict(X_scaled)[0] == -1)

        # Top contributing features
        sorted_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        top_factors = sorted_importances[:5]

        # Feature-specific evidence
        evidence = []
        feat_vals = {col: float(features.get(col, 0.0)) for col in FEATURE_COLUMNS}
        if feat_vals.get("CYCLO", 0) > 0.6:
            evidence.append(f"High cyclomatic complexity ({feat_vals['CYCLO']:.2f})")
        if feat_vals.get("VOLUME", 0) > 0.7:
            evidence.append(f"High Halstead volume ({feat_vals['VOLUME']:.2f})")
        if feat_vals.get("DIFFICULTY", 0) > 0.6:
            evidence.append(f"High code difficulty ({feat_vals['DIFFICULTY']:.2f})")
        if feat_vals.get("LOC", 0) > 0.7:
            evidence.append(f"High lines of code ({feat_vals['LOC']:.2f})")
        if not evidence:
            evidence.append("Metrics within typical ranges")

        return {
            "prediction": pred,
            "prediction_label": LABEL_NAMES.get(pred, "Unknown"),
            "defect_probability": round(prob, 4),
            "risk_category": risk_category,
            "model_used": model_name,
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anom_score, 4),
            "top_contributing_factors": dict(top_factors),
            "evidence": evidence,
            "input_features": feat_vals,
            "label_semantics": LABEL_NAMES,
            "trained_at": self.trained_at,
        }

    def detect_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Runs anomaly detection on a batch of components."""
        if self.scaler is None:
            if not self.load_bundle():
                return []

        X = df[FEATURE_COLUMNS].fillna(0.0)
        X_scaled = self.scaler.transform(X)
        scores = self.isolation_forest.decision_function(X_scaled)
        preds = self.isolation_forest.predict(X_scaled)

        anomalies = []
        for i in range(len(df)):
            if preds[i] == -1:
                anomalies.append({
                    "index": i,
                    "anomaly_score": round(float(scores[i]), 4),
                    "features": {col: round(float(X.iloc[i][col]), 4) for col in FEATURE_COLUMNS},
                })
        return anomalies
