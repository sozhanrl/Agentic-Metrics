"""
test_ml_intelligence.py
------------------------
Automated test suite verifying the ML/DL Software Metrics Intelligence Platform:
1. Feature engineering, preprocessing & chronological split
2. Model Group A: Code Quality Intelligence (RF, XGBoost, Isolation Forest, Classifier)
3. Model Group B: Process Intelligence (RF, XGBoost, ARIMA, Delay Risk)
4. Model Group C: DevOps Intelligence (Pre-deployment only, XGBoost, MTTR)
5. Deep Learning Strategy Evaluator (Section 4 compliance)
6. Explainable Recommendation Bridge (Evidence, actions, hypotheses)
7. ML API Endpoints
"""

import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.ml.feature_engineering import (
    CodeQualityFeatureExtractor,
    ProcessFeatureExtractor,
    DevOpsFeatureExtractor,
    create_preprocessor,
    chronological_split,
)
from app.ml.code_quality_pipeline import CodeQualityIntelligence
from app.ml.process_pipeline import ProcessIntelligence
from app.ml.devops_pipeline import DevOpsIntelligence
from app.ml.deep_learning_evaluator import DeepLearningStrategyEvaluator
from app.ml.recommendation_bridge import ExplainableRecommendationGenerator


client = TestClient(app)


def test_code_quality_feature_extraction():
    df = pd.DataFrame([
        {"code_churn": 25.0, "cyclomatic_complexity": 18.0, "test_coverage": 55.0},
        {"code_churn": 22.0, "cyclomatic_complexity": 16.0, "test_coverage": 60.0},
    ])
    X, names = CodeQualityFeatureExtractor.build_features(df)
    assert X.shape == (2, len(CodeQualityFeatureExtractor.FEATURE_NAMES))
    assert "complexity_churn_interaction" in names
    assert not np.isnan(X).any()


def test_chronological_split_preserves_temporal_order():
    X = np.arange(20).reshape(-1, 1)
    y = np.arange(20)
    X_train, X_test, y_train, y_test = chronological_split(X, y, test_size=0.25)
    assert len(X_train) == 15
    assert len(X_test) == 5
    assert y_train[-1] < y_test[0]  # Strict temporal boundary, no future leakage


def test_deep_learning_evaluation_criteria():
    small_eval = DeepLearningStrategyEvaluator.evaluate_dataset_sufficiency(n_samples=50)
    assert small_eval["dl_available"] is False
    assert "Insufficient Training Data" in small_eval["status"]
    assert "Tree-Based Ensemble" in small_eval["selected_paradigm"]

    large_eval = DeepLearningStrategyEvaluator.evaluate_dataset_sufficiency(n_samples=300)
    assert large_eval["dl_available"] is True


def test_code_quality_pipeline_training(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    pipeline = CodeQualityIntelligence(artifacts_dir)

    # 15 observations with diverse quality signals
    df = pd.DataFrame({
        "code_churn": [15, 20, 25, 30, 18, 22, 28, 16, 24, 29, 14, 19, 23, 27, 31],
        "cyclomatic_complexity": [10, 12, 16, 20, 11, 14, 18, 9, 15, 19, 8, 13, 17, 21, 22],
        "test_coverage": [85, 80, 65, 50, 82, 75, 60, 88, 70, 55, 90, 78, 68, 52, 48],
        "defect_density": [0.8, 1.1, 1.8, 2.5, 0.9, 1.3, 2.0, 0.7, 1.4, 2.3, 0.6, 1.2, 1.9, 2.6, 2.8],
    })

    eval_res = pipeline.train_models(df)
    assert "xgboost_regressor" in eval_res
    assert "random_forest_regressor" in eval_res
    assert eval_res["xgboost_regressor"]["mae"] >= 0.0

    # Test inference
    pred = pipeline.predict({"code_churn": 25.0, "cyclomatic_complexity": 18.0, "test_coverage": 60.0})
    assert pred["target_metric"] == "defect_density"
    assert pred["predicted_value"] > 0
    assert pred["risk_level"] in ["low", "medium", "high"]
    assert len(pred["recommended_actions"]) > 0


def test_process_pipeline_training(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    pipeline = ProcessIntelligence(artifacts_dir)

    df = pd.DataFrame({
        "sprint_velocity": [20, 22, 25, 24, 26, 28, 27, 29, 31, 30, 32, 33],
        "cycle_time": [6, 5.5, 5, 4.8, 4.5, 4.2, 4.0, 3.8, 3.5, 3.6, 3.4, 3.2],
        "lead_time": [14, 13, 12, 11, 10, 9.5, 9, 8.5, 8, 8.2, 7.8, 7.5],
        "wip": [12, 11, 10, 9, 8, 8, 7, 7, 6, 6, 5, 5],
    })

    eval_res = pipeline.train_models(df)
    assert "random_forest_regressor" in eval_res
    assert "time_series_baseline_mae" in eval_res

    pred = pipeline.predict({"sprint_velocity": 30.0, "wip": 8.0, "cycle_time": 4.0})
    assert "predicted_velocity" in pred
    assert pred["predicted_velocity"] > 0


def test_devops_pipeline_training(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    pipeline = DevOpsIntelligence(artifacts_dir)

    df = pd.DataFrame({
        "change_failure_rate": [10, 12, 15, 22, 28, 14, 18, 25, 30, 11, 16, 24],
        "mttr": [3.0, 3.5, 4.0, 6.5, 8.0, 4.2, 5.0, 7.2, 9.0, 3.2, 4.8, 6.8],
        "deployment_frequency": [3.0, 2.8, 2.5, 1.2, 0.8, 2.2, 1.8, 1.0, 0.6, 3.2, 2.0, 1.1],
        "code_churn": [12, 15, 18, 26, 32, 16, 20, 28, 34, 11, 19, 27],
        "test_coverage": [85, 82, 78, 62, 54, 76, 70, 58, 50, 88, 72, 60],
        "cyclomatic_complexity": [10, 11, 13, 17, 21, 12, 15, 18, 22, 9, 14, 19],
    })

    eval_res = pipeline.train_models(df)
    assert "xgboost_classifier" in eval_res
    assert "mttr_regressor" in eval_res

    pred = pipeline.predict({"change_failure_rate": 25.0, "deployment_frequency": 1.2})
    assert "predicted_failure_probability" in pred
    assert 0.0 <= pred["predicted_failure_probability"] <= 1.0


def test_recommendation_bridge_evidence_and_hypothesis():
    recs = ExplainableRecommendationGenerator.generate_recommendations(
        metrics={"test_coverage": 50.0, "cyclomatic_complexity": 18.0, "wip": 12.0},
        predictions={"process": {"delay_risk": "high"}},
    )
    assert len(recs) >= 2
    for r in recs:
        assert "evidence" in r and len(r["evidence"]) > 10
        assert "suggested_action" in r
        assert "Hypothesis:" in r["expected_outcome_hypothesis"]


def test_ml_api_status_endpoint():
    resp = client.get("/api/ml/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["operational", "initialization_needed"]
    assert "deep_learning_status" in data
    assert isinstance(data["algorithms"], list)


def test_ml_api_models_and_performance():
    r1 = client.get("/api/ml/models")
    assert r1.status_code == 200
    assert isinstance(r1.json(), list)

    r2 = client.get("/api/ml/performance")
    assert r2.status_code == 200
    assert isinstance(r2.json(), dict)


def test_ml_api_predictions_and_modules():
    # Test for project 2
    r_preds = client.get("/api/ml/predictions/2")
    assert r_preds.status_code == 200
    assert isinstance(r_preds.json(), list)

    r_mods = client.get("/api/ml/modules/2")
    assert r_mods.status_code == 200
    assert isinstance(r_mods.json(), list)

    r_recs = client.get("/api/ml/recommendations/2")
    assert r_recs.status_code == 200
    assert isinstance(r_recs.json(), list)


def test_ml_api_on_demand_predict():
    payload = {
        "project_id": 2,
        "category": "code_quality",
        "features": {
            "code_churn": 24.0,
            "cyclomatic_complexity": 17.5,
            "test_coverage": 58.0,
        },
    }
    resp = client.post("/api/ml/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_value" in data
    assert "risk_level" in data
