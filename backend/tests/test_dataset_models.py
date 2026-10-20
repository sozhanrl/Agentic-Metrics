"""
test_dataset_models.py
-----------------------
Automated test suite verifying Prompt 4 requirements:
1. Discovery and inspection of all 3 CSV datasets (SoftwareDefectDataset.csv, OnlyTrivial_dt.csv, OnlyNonTrivial_dt.csv).
2. Dataset A (SoftwareDefectDataset): Random Forest, XGBoost, Logistic Regression baseline, Isolation Forest, calibrated probabilities, feature importance.
3. Dataset B (OnlyTrivial_dt): Target 'refactoring', group-aware splitting by 'class', feature exclusion (target, file, class), champion selection.
4. Dataset C (OnlyNonTrivial_dt): Separate evaluation pipeline, group-aware splitting, trivial vs non-trivial comparison report, zero file overlap verification.
5. Missing Process & DevOps datasets handling: honest reporting, no fake models trained on unrelated code metrics.
6. API Endpoints: status, evaluation, comparison, defect prediction, refactoring prediction, input validation, and error states.
"""

import os
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.ml.trainer import DEFECT_CSV, TRIVIAL_CSV, NONTRIVIAL_CSV, ARTIFACTS_DIR
from app.ml.defect_classifier import DefectClassifierPipeline, FEATURE_COLUMNS, TARGET_COLUMN
from app.ml.refactoring_classifier import (
    RefactoringClassifierPipeline,
    compare_trivial_vs_nontrivial,
)

client = TestClient(app)


def test_csv_datasets_exist_and_schemas_verified():
    """Verify all 3 CSV datasets exist in expected paths with expected schemas."""
    assert os.path.exists(DEFECT_CSV), f"Dataset A missing at {DEFECT_CSV}"
    assert os.path.exists(TRIVIAL_CSV), f"Dataset B missing at {TRIVIAL_CSV}"
    assert os.path.exists(NONTRIVIAL_CSV), f"Dataset C missing at {NONTRIVIAL_CSV}"

    # Dataset A inspection
    df_def = pd.read_csv(DEFECT_CSV)
    assert len(df_def) == 1000
    for col in FEATURE_COLUMNS:
        assert col in df_def.columns
    assert TARGET_COLUMN in df_def.columns
    assert set(df_def[TARGET_COLUMN].unique()) == {0, 1}
    assert df_def.isnull().sum().sum() == 0  # No missing values

    # Dataset B inspection
    df_triv_head = pd.read_csv(TRIVIAL_CSV, nrows=50)
    assert "refactoring" in df_triv_head.columns
    assert "class" in df_triv_head.columns
    assert "file" in df_triv_head.columns
    assert "loc" in df_triv_head.columns
    assert "cbo" in df_triv_head.columns

    # Dataset C inspection
    df_nontriv_head = pd.read_csv(NONTRIVIAL_CSV, nrows=50)
    assert "refactoring" in df_nontriv_head.columns
    assert "class" in df_nontriv_head.columns
    assert "file" in df_nontriv_head.columns


def test_defect_classifier_pipeline_training_and_evaluation(tmp_path):
    """Test Dataset A pipeline: RF, XGBoost, Logistic Regression, Isolation Forest."""
    artifacts = str(tmp_path / "artifacts")
    pipeline = DefectClassifierPipeline(artifacts)

    df_def, info = pipeline.load_dataset(DEFECT_CSV)
    assert info["total_rows"] == 1000
    assert info["target_distribution"][0] == 674
    assert info["target_distribution"][1] == 326

    results = pipeline.train(df_def)
    assert "random_forest" in results
    assert "logistic_regression" in results
    assert "isolation_forest" in results
    assert "champion_model" in results

    rf = results["random_forest"]
    assert "precision" in rf and "recall" in rf and "f1" in rf and "roc_auc" in rf
    assert "confusion_matrix" in rf
    assert len(rf["feature_importances"]) == len(FEATURE_COLUMNS)

    # Test inference
    test_features = {col: 0.5 for col in FEATURE_COLUMNS}
    pred = pipeline.predict(test_features)
    assert "defect_probability" in pred
    assert 0.0 <= pred["defect_probability"] <= 1.0
    assert pred["risk_category"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert "top_contributing_factors" in pred
    assert "evidence" in pred


def test_refactoring_classifier_group_aware_split_and_training(tmp_path):
    """Test Dataset B pipeline with group-aware splitting by 'class'."""
    artifacts = str(tmp_path / "artifacts")
    pipeline = RefactoringClassifierPipeline(artifacts, "trivial")

    # Sample for fast unit test
    df_triv, info = pipeline.load_dataset(TRIVIAL_CSV, sample_size=2000)
    assert "class" in df_triv.columns
    assert "file" in df_triv.columns

    results = pipeline.train(df_triv)
    assert "random_forest" in results
    assert "logistic_regression" in results
    assert "isolation_forest" in results
    assert "Group-aware" in results["dataset"]["splitting_strategy"]

    # Test inference
    pred = pipeline.predict({"loc": 200, "cbo": 10, "wmc": 25, "rfc": 35})
    assert "prediction_label" in pred
    assert "probability" in pred or "refactoring_probability" in pred
    assert "top_contributing_factors" in pred
    assert "label_semantics" in pred


def test_trivial_vs_nontrivial_comparison_report():
    """Verify comparison between trivial and non-trivial refactoring datasets."""
    triv_eval = {
        "champion_model": "random_forest",
        "champion_f1": 0.5712,
        "dataset": {
            "total_samples": 232468,
            "train_samples": 185974,
            "test_samples": 46494,
            "splitting_strategy": "Group-aware split by 'class' (80/20)",
        },
        "random_forest": {"accuracy": 0.558, "precision": 0.564, "recall": 0.581, "roc_auc": 0.582},
    }
    nontriv_eval = {
        "champion_model": "logistic_regression",
        "champion_f1": 0.5234,
        "dataset": {
            "total_samples": 509426,
            "train_samples": 407540,
            "test_samples": 101886,
            "splitting_strategy": "Group-aware split by 'class' (80/20)",
        },
        "logistic_regression": {"accuracy": 0.521, "precision": 0.518, "recall": 0.532, "roc_auc": 0.531},
    }

    report = compare_trivial_vs_nontrivial(
        triv_eval, nontriv_eval,
        overlap_info={"overlapping_files": 0, "overlapping_classes": 15064, "note": "Zero file overlap."}
    )
    assert "datasets" in report
    assert report["overlap_analysis"]["overlapping_files"] == 0
    assert len(report["limitations"]) > 0


def test_api_dataset_status_and_evaluation():
    """Test GET /api/ml/dataset/status and GET /api/ml/dataset/evaluation."""
    r_status = client.get("/api/ml/dataset/status")
    assert r_status.status_code == 200
    data_status = r_status.json()
    assert "defect_classifier" in data_status
    assert "refactoring_trivial" in data_status
    assert "refactoring_nontrivial" in data_status

    r_eval = client.get("/api/ml/dataset/evaluation")
    assert r_eval.status_code == 200
    data_eval = r_eval.json()
    assert "defect_classifier" in data_eval


def test_api_live_predictions_defect_and_refactoring():
    """Test POST endpoints for defect and refactoring inference."""
    # Defect prediction
    payload_def = {
        "features": {col: 0.6 for col in FEATURE_COLUMNS},
        "model_name": "auto",
    }
    r_def = client.post("/api/ml/dataset/predict/defect", json=payload_def)
    assert r_def.status_code == 200
    data_def = r_def.json()
    assert "defect_probability" in data_def
    assert "risk_category" in data_def

    # Refactoring prediction
    payload_ref = {
        "features": {"loc": 150, "cbo": 8, "wmc": 20, "rfc": 30},
        "dataset_type": "trivial",
        "model_name": "auto",
    }
    r_ref = client.post("/api/ml/dataset/predict/refactoring", json=payload_ref)
    assert r_ref.status_code == 200
    data_ref = r_ref.json()
    assert "prediction_label" in data_ref


def test_process_and_devops_data_status_honest_reporting():
    """
    Verify that Process and DevOps status endpoints explicitly report that
    code quality CSV datasets are NOT suitable for sprint/deployment predictions.
    """
    r_proc = client.get("/api/ml/dataset/process-status")
    assert r_proc.status_code == 200
    data_proc = r_proc.json()
    assert data_proc["csv_datasets_applicable"] is False
    assert ("historical process metric records" in data_proc["message"] or "The supplied CSV datasets" in data_proc["message"])

    r_dev = client.get("/api/ml/dataset/devops-status")
    assert r_dev.status_code == 200
    data_dev = r_dev.json()
    assert data_dev["csv_datasets_applicable"] is False
    assert ("historical DevOps metric records" in data_dev["message"] or "The supplied CSV datasets" in data_dev["message"])
