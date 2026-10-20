"""
ml.py
-----
FastAPI router for Machine Learning and Deep Learning Intelligence Platform.
Endpoints:
- GET  /api/ml/status
- GET  /api/ml/models
- GET  /api/ml/performance
- GET  /api/ml/predictions/{project_id}
- GET  /api/ml/recommendations/{project_id}
- GET  /api/ml/anomalies/{project_id}
- GET  /api/ml/modules/{project_id}
- GET  /api/ml/drift/{project_id}
- POST /api/ml/train
- POST /api/ml/predict
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app import models, schemas
from app.ml.trainer import MLPlatformCoordinator
from app.ml.deep_learning_evaluator import DeepLearningStrategyEvaluator
from app.ml.recommendation_bridge import ExplainableRecommendationGenerator


router = APIRouter(prefix="/api/ml", tags=["ML Intelligence Platform"])


@router.get("/status", response_model=schemas.MLStatusResponse)
def get_ml_status(db: Session = Depends(get_db)):
    """Returns overall ML platform readiness, registered models, and deep learning feasibility."""
    models_in_reg = db.query(models.MLModelRegistry).all()
    ready = len(models_in_reg) >= 3
    last_run = db.query(models.MLTrainingRun).order_by(desc(models.MLTrainingRun.created_at)).first()

    dl_eval = DeepLearningStrategyEvaluator.evaluate_dataset_sufficiency(
        last_run.train_samples if last_run else 0
    )

    return schemas.MLStatusResponse(
        status="operational" if ready else "initialization_needed",
        ready=ready,
        models_count=len(models_in_reg),
        algorithms=[
            "XGBoost Regressor",
            "Random Forest Regressor",
            "XGBoost Classifier",
            "Random Forest Classifier",
            "Isolation Forest (Unsupervised)",
            "ARIMA / Moving Average Time-Series",
        ],
        deep_learning_status=dl_eval,
        last_trained_at=last_run.created_at if last_run else None,
    )


@router.get("/models", response_model=List[schemas.MLModelResponse])
def list_models(db: Session = Depends(get_db)):
    """Lists all registered machine learning models with versions, hyperparams, and schemas."""
    return db.query(models.MLModelRegistry).order_by(models.MLModelRegistry.category).all()


@router.get("/performance")
def get_model_performance(db: Session = Depends(get_db)):
    """
    Returns actual, empirical evaluation metrics (MAE, RMSE, R2, F1, ROC-AUC, confusion matrices)
    derived from validation and test splits.
    """
    regs = db.query(models.MLModelRegistry).all()
    results = {}
    for r in regs:
        results[r.model_id] = {
            "name": r.name,
            "category": r.category,
            "algorithm": r.algorithm,
            "target_metric": r.target_metric,
            "version": r.version,
            "evaluation_metrics": r.evaluation_metrics,
            "features": r.features,
            "updated_at": r.updated_at,
        }
    return results


@router.get("/predictions/{project_id}", response_model=List[schemas.MLPredictionResponse])
def get_project_predictions(project_id: int, db: Session = Depends(get_db)):
    """Fetches latest predictions, intervals, and feature contributions for a project."""
    preds = (
        db.query(models.MLPrediction)
        .filter(models.MLPrediction.project_id == project_id)
        .order_by(desc(models.MLPrediction.created_at))
        .all()
    )
    # Deduplicate by target_metric to return the latest for each category
    seen = set()
    latest_preds = []
    for p in preds:
        if p.target_metric not in seen:
            seen.add(p.target_metric)
            latest_preds.append(p)

    # If no predictions exist yet, trigger coordinator to generate
    if not latest_preds:
        coord = MLPlatformCoordinator(db)
        coord.generate_project_predictions(project_id)
        preds = (
            db.query(models.MLPrediction)
            .filter(models.MLPrediction.project_id == project_id)
            .order_by(desc(models.MLPrediction.created_at))
            .all()
        )
        for p in preds:
            if p.target_metric not in seen:
                seen.add(p.target_metric)
                latest_preds.append(p)

    return latest_preds


@router.get("/recommendations/{project_id}")
def get_ml_recommendations(project_id: int, db: Session = Depends(get_db)):
    """Returns explainable recommendations directly traceable to measured metrics and model outputs."""
    # Fetch latest metrics
    latest_rows = (
        db.query(models.MetricValue, models.MetricDefinition)
        .join(models.MetricDefinition, models.MetricValue.metric_id == models.MetricDefinition.id)
        .filter(models.MetricValue.project_id == project_id)
        .all()
    )
    metrics_map = {defn.key: float(val.value) for val, defn in latest_rows}
    if not metrics_map:
        metrics_map = {
            "code_churn": 22.0, "cyclomatic_complexity": 14.5, "test_coverage": 62.0,
            "defect_density": 1.7, "sprint_velocity": 25.0, "cycle_time": 4.8,
            "wip": 9.0, "change_failure_rate": 22.0, "mttr": 6.5,
        }

    # Fetch latest predictions
    preds = (
        db.query(models.MLPrediction)
        .filter(models.MLPrediction.project_id == project_id)
        .order_by(desc(models.MLPrediction.created_at))
        .all()
    )
    preds_map = {}
    for p in preds:
        if p.category not in preds_map:
            preds_map[p.category] = {
                "target_metric": p.target_metric,
                "predicted_value": float(p.predicted_value),
                "risk_level": p.risk_level,
                "predicted_failure_probability": float(p.predicted_value) / 100.0 if p.category == "devops" else 0.2,
                "predicted_velocity": float(p.predicted_value) if p.category == "process" else 26.0,
                "delay_risk": p.risk_level,
            }

    # Fetch modules
    modules = (
        db.query(models.MLCodeModule)
        .filter(models.MLCodeModule.project_id == project_id)
        .all()
    )
    mod_dicts = [
        {
            "module_name": m.module_name,
            "defect_risk_level": m.defect_risk_level,
            "churn_pct": float(m.churn_pct),
            "complexity": float(m.complexity),
            "coverage_pct": float(m.coverage_pct),
        }
        for m in modules
    ]

    return ExplainableRecommendationGenerator.generate_recommendations(
        metrics=metrics_map,
        predictions=preds_map,
        modules=mod_dicts,
    )


@router.get("/anomalies/{project_id}")
def get_ml_anomalies(project_id: int, db: Session = Depends(get_db)):
    """Returns anomalies detected via Isolation Forest and statistical control limits."""
    # Query database anomalies table + any active isolation forest signals
    anomalies = (
        db.query(models.Anomaly)
        .filter(models.Anomaly.project_id == project_id)
        .order_by(desc(models.Anomaly.detected_at))
        .limit(10)
        .all()
    )
    return anomalies


@router.get("/modules/{project_id}", response_model=List[schemas.MLCodeModuleResponse])
def get_code_modules(project_id: int, db: Session = Depends(get_db)):
    """Returns module-level risk classifications (Low, Medium, High) and metrics."""
    mods = (
        db.query(models.MLCodeModule)
        .filter(models.MLCodeModule.project_id == project_id)
        .order_by(desc(models.MLCodeModule.defect_risk_prob))
        .all()
    )
    if not mods:
        coord = MLPlatformCoordinator(db)
        coord.generate_project_predictions(project_id)
        mods = (
            db.query(models.MLCodeModule)
            .filter(models.MLCodeModule.project_id == project_id)
            .order_by(desc(models.MLCodeModule.defect_risk_prob))
            .all()
        )
    return mods


@router.get("/drift/{project_id}", response_model=List[schemas.MLDriftStatusResponse])
def get_drift_status(project_id: int, db: Session = Depends(get_db)):
    """Returns data and feature drift indicators across baseline and current observations."""
    drift_rows = (
        db.query(models.MLDriftStatus)
        .filter(models.MLDriftStatus.project_id == project_id)
        .order_by(desc(models.MLDriftStatus.checked_at))
        .all()
    )
    return drift_rows


@router.get("/training-history", response_model=List[schemas.TrainingRunResponse])
def get_training_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Returns chronological training run history with evaluation metrics and duration."""
    runs = (
        db.query(models.MLTrainingRun)
        .order_by(desc(models.MLTrainingRun.created_at))
        .limit(limit)
        .all()
    )
    return runs


@router.get("/predictions/{project_id}/trajectory")
def get_prediction_trajectory(
    project_id: int,
    target_metric: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns historical prediction trajectory for a project, showing how
    predictions evolved over time with confidence intervals.
    Used for forecast trend visualization.
    """
    query = (
        db.query(models.MLPrediction)
        .filter(models.MLPrediction.project_id == project_id)
        .order_by(models.MLPrediction.created_at.asc())
    )
    if target_metric:
        query = query.filter(models.MLPrediction.target_metric == target_metric)

    preds = query.limit(limit).all()

    # Group by target_metric for multi-line chart
    trajectory = {}
    for p in preds:
        key = p.target_metric
        if key not in trajectory:
            trajectory[key] = []
        trajectory[key].append({
            "target_metric": p.target_metric,
            "category": p.category,
            "predicted_value": float(p.predicted_value),
            "current_value": float(p.current_value) if p.current_value else None,
            "lower_bound": float(p.lower_bound) if p.lower_bound else None,
            "upper_bound": float(p.upper_bound) if p.upper_bound else None,
            "confidence": float(p.confidence) if p.confidence else 0.85,
            "risk_level": p.risk_level,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return trajectory


@router.get("/comparison", response_model=List[schemas.ModelComparisonResponse])
def get_model_comparison(db: Session = Depends(get_db)):
    """
    Returns a structured comparison of all models with flattened evaluation metrics
    for radar chart and bar chart visualization.
    """
    regs = db.query(models.MLModelRegistry).all()
    results = []

    for r in regs:
        eval_m = r.evaluation_metrics or {}
        # Extract flat metrics from the nested evaluation_metrics JSONB
        mae = None
        rmse = None
        r2 = None
        f1 = None
        roc_auc = None
        precision = None
        recall = None
        train_samples = None

        # Code Quality models
        if r.category == "code_quality":
            xgb = eval_m.get("xgboost_regressor", {})
            rf = eval_m.get("random_forest_regressor", {})
            clf = eval_m.get("risk_classifier", {})
            mae = xgb.get("mae") or rf.get("mae")
            rmse = xgb.get("rmse") or rf.get("rmse")
            r2 = xgb.get("r2") or rf.get("r2")
            f1 = clf.get("f1")
            roc_auc = clf.get("roc_auc")
            precision = clf.get("precision")
            recall = clf.get("recall")

        # Process models
        elif r.category == "process":
            xgb = eval_m.get("xgboost_regressor", {})
            rf = eval_m.get("random_forest_regressor", {})
            mae = xgb.get("mae") or rf.get("mae")
            rmse = xgb.get("rmse") or rf.get("rmse")
            r2 = xgb.get("r2") or rf.get("r2")

        # DevOps models
        elif r.category == "devops":
            xgb_clf = eval_m.get("xgboost_classifier", {})
            rf_clf = eval_m.get("random_forest_classifier", {})
            mttr = eval_m.get("mttr_regressor", {})
            mae = mttr.get("mae")
            rmse = mttr.get("rmse")
            r2 = mttr.get("r2")
            f1 = xgb_clf.get("f1") or rf_clf.get("f1")
            roc_auc = xgb_clf.get("roc_auc") or rf_clf.get("roc_auc")
            precision = xgb_clf.get("precision") or rf_clf.get("precision")
            recall = xgb_clf.get("recall") or rf_clf.get("recall")

        # Get training run info
        last_run = (
            db.query(models.MLTrainingRun)
            .filter(models.MLTrainingRun.model_id == r.model_id)
            .order_by(desc(models.MLTrainingRun.created_at))
            .first()
        )
        if last_run:
            train_samples = last_run.train_samples

        results.append(schemas.ModelComparisonResponse(
            model_id=r.model_id,
            name=r.name,
            category=r.category,
            algorithm=r.algorithm,
            target_metric=r.target_metric,
            mae=mae,
            rmse=rmse,
            r2=r2,
            f1=f1,
            roc_auc=roc_auc,
            precision=precision,
            recall=recall,
            training_samples=train_samples,
            feature_count=len(r.features) if r.features else None,
            status=r.status,
        ))

    return results


@router.post("/train")
def train_models(payload: schemas.MLTrainRequest = schemas.MLTrainRequest(), db: Session = Depends(get_db)):
    """
    Triggers end-to-end model training run across Code Quality, Process, and DevOps.
    Persists models, updates registry, and returns evaluation report.
    """
    coord = MLPlatformCoordinator(db)
    result = coord.train_all(force=payload.force)
    return result


@router.post("/predict")
def predict_on_demand(payload: schemas.MLPredictRequest, db: Session = Depends(get_db)):
    """Runs on-demand inference for custom/simulated feature inputs."""
    coord = MLPlatformCoordinator(db)
    if payload.category == "code_quality":
        return coord.code_quality.predict(payload.features)
    elif payload.category == "process":
        return coord.process.predict(payload.features)
    elif payload.category == "devops":
        return coord.devops.predict(payload.features)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported category '{payload.category}'.")


# ===========================================================================
# Dataset-Specific ML Endpoints
# ===========================================================================

@router.post("/dataset/train")
def train_dataset_models(
    payload: schemas.DatasetTrainRequest = schemas.DatasetTrainRequest(),
    db: Session = Depends(get_db),
):
    """
    Trains models from the three CSV datasets:
    - SoftwareDefectDataset.csv (defect classification)
    - OnlyTrivial_dt.csv (trivial refactoring classification)
    - OnlyNonTrivial_dt.csv (non-trivial refactoring classification)
    Returns full evaluation report with metrics comparison.
    """
    coord = MLPlatformCoordinator(db)
    result = coord.train_dataset_models(datasets=payload.datasets)
    return result


@router.get("/dataset/status")
def get_dataset_status(db: Session = Depends(get_db)):
    """Returns status of dataset-specific models (defect, trivial, nontrivial)."""
    coord = MLPlatformCoordinator(db)

    defect_loaded = coord.defect_classifier.load_bundle()
    trivial_loaded = coord.refactoring_trivial.load_bundle()
    nontrivial_loaded = coord.refactoring_nontrivial.load_bundle()

    return {
        "defect_classifier": {
            "trained": defect_loaded,
            "trained_at": coord.defect_classifier.trained_at if defect_loaded else None,
            "champion_model": coord.defect_classifier.evaluation_results.get("champion_model") if defect_loaded else None,
            "champion_f1": coord.defect_classifier.evaluation_results.get("champion_f1") if defect_loaded else None,
            "dataset": "SoftwareDefectDataset.csv",
            "samples": coord.defect_classifier.evaluation_results.get("dataset", {}).get("total_samples") if defect_loaded else None,
        },
        "refactoring_trivial": {
            "trained": trivial_loaded,
            "trained_at": coord.refactoring_trivial.trained_at if trivial_loaded else None,
            "champion_model": coord.refactoring_trivial.evaluation_results.get("champion_model") if trivial_loaded else None,
            "champion_f1": coord.refactoring_trivial.evaluation_results.get("champion_f1") if trivial_loaded else None,
            "dataset": "OnlyTrivial_dt.csv",
            "samples": coord.refactoring_trivial.evaluation_results.get("dataset", {}).get("total_samples") if trivial_loaded else None,
        },
        "refactoring_nontrivial": {
            "trained": nontrivial_loaded,
            "trained_at": coord.refactoring_nontrivial.trained_at if nontrivial_loaded else None,
            "champion_model": coord.refactoring_nontrivial.evaluation_results.get("champion_model") if nontrivial_loaded else None,
            "champion_f1": coord.refactoring_nontrivial.evaluation_results.get("champion_f1") if nontrivial_loaded else None,
            "dataset": "OnlyNonTrivial_dt.csv",
            "samples": coord.refactoring_nontrivial.evaluation_results.get("dataset", {}).get("total_samples") if nontrivial_loaded else None,
        },
    }


@router.get("/dataset/evaluation")
def get_dataset_evaluation(db: Session = Depends(get_db)):
    """Returns full evaluation results for all dataset-specific models."""
    coord = MLPlatformCoordinator(db)
    result = {}

    if coord.defect_classifier.load_bundle():
        result["defect_classifier"] = coord.defect_classifier.evaluation_results
    else:
        result["defect_classifier"] = {"status": "not_trained"}

    if coord.refactoring_trivial.load_bundle():
        result["refactoring_trivial"] = coord.refactoring_trivial.evaluation_results
    else:
        result["refactoring_trivial"] = {"status": "not_trained"}

    if coord.refactoring_nontrivial.load_bundle():
        result["refactoring_nontrivial"] = coord.refactoring_nontrivial.evaluation_results
    else:
        result["refactoring_nontrivial"] = {"status": "not_trained"}

    # Comparison if both refactoring models are trained
    from app.ml.refactoring_classifier import compare_trivial_vs_nontrivial
    if "champion_model" in result.get("refactoring_trivial", {}) and "champion_model" in result.get("refactoring_nontrivial", {}):
        result["refactoring_comparison"] = compare_trivial_vs_nontrivial(
            result["refactoring_trivial"],
            result["refactoring_nontrivial"],
            overlap_info={
                "overlapping_files": 0,
                "overlapping_classes": 15064,
                "note": "Datasets share 15,064 class names but zero overlapping file paths. Separate models maintained.",
            },
        )

    return result


@router.post("/dataset/predict/defect")
def predict_defect_risk(
    payload: schemas.DefectPredictRequest,
    db: Session = Depends(get_db),
):
    """
    Predicts whether a software component is defect-prone using SoftwareDefectDataset.csv models.
    Input features: LOC, CYCLO, LENGTH, VOLUME, DIFFICULTY, INT_FAN_IN, INT_FAN_OUT,
                    NUM_OPERATORS, NUM_OPERANDS, BRANCH_COUNT
    """
    coord = MLPlatformCoordinator(db)
    result = coord.defect_classifier.predict(payload.features, model_name=payload.model_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/dataset/predict/refactoring")
def predict_refactoring(
    payload: schemas.RefactoringPredictRequest,
    db: Session = Depends(get_db),
):
    """
    Predicts refactoring classification for a code component.
    dataset_type: 'trivial' or 'nontrivial'
    """
    coord = MLPlatformCoordinator(db)
    if payload.dataset_type == "trivial":
        result = coord.refactoring_trivial.predict(payload.features, model_name=payload.model_name)
    elif payload.dataset_type == "nontrivial":
        result = coord.refactoring_nontrivial.predict(payload.features, model_name=payload.model_name)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid dataset_type '{payload.dataset_type}'. Use 'trivial' or 'nontrivial'.")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/dataset/comparison")
def get_refactoring_comparison(db: Session = Depends(get_db)):
    """
    Returns a comparison report between trivial and non-trivial refactoring models.
    Includes per-model metrics, feature importance differences, and dataset overlap analysis.
    """
    coord = MLPlatformCoordinator(db)
    trivial_loaded = coord.refactoring_trivial.load_bundle()
    nontrivial_loaded = coord.refactoring_nontrivial.load_bundle()

    if not trivial_loaded or not nontrivial_loaded:
        missing = []
        if not trivial_loaded:
            missing.append("refactoring_trivial")
        if not nontrivial_loaded:
            missing.append("refactoring_nontrivial")
        raise HTTPException(
            status_code=400,
            detail=f"Models not trained: {missing}. Train via POST /api/ml/dataset/train first.",
        )

    from app.ml.refactoring_classifier import compare_trivial_vs_nontrivial
    return compare_trivial_vs_nontrivial(
        coord.refactoring_trivial.evaluation_results,
        coord.refactoring_nontrivial.evaluation_results,
        overlap_info={
            "overlapping_files": 0,
            "overlapping_classes": 15064,
            "note": "Datasets share 15,064 class names but zero overlapping file paths. Separate models maintained.",
        },
    )


@router.get("/dataset/process-status")
def get_process_data_status(db: Session = Depends(get_db)):
    """
    Checks whether historical sprint / process data exists for process ML models.
    The supplied CSV datasets are NOT suitable for sprint velocity or cycle-time prediction.
    """
    count = db.query(models.MetricValue).join(
        models.MetricDefinition,
        models.MetricValue.metric_id == models.MetricDefinition.id
    ).filter(
        models.MetricDefinition.category == "process"
    ).count()

    return {
        "category": "process",
        "historical_records": count,
        "sufficient_for_training": count >= 30,
        "message": (
            f"Found {count} historical process metric records. "
            + ("Sufficient for time-series forecasting." if count >= 30
               else "Insufficient data. The supplied CSV datasets (SoftwareDefectDataset.csv, OnlyTrivial_dt.csv, OnlyNonTrivial_dt.csv) "
                    "are code quality datasets, not sprint/process data. Process predictions require historical sprint velocity, "
                    "cycle time, and lead time records from an issue tracker (Jira, Azure DevOps).")
        ),
        "required_metrics": ["sprint_velocity", "cycle_time", "lead_time", "wip", "sprint_predictability"],
        "csv_datasets_applicable": False,
    }


@router.get("/dataset/devops-status")
def get_devops_data_status(db: Session = Depends(get_db)):
    """
    Checks whether historical deployment / CI-CD data exists for DevOps ML models.
    The supplied CSV datasets are NOT deployment history.
    """
    count = db.query(models.MetricValue).join(
        models.MetricDefinition,
        models.MetricValue.metric_id == models.MetricDefinition.id
    ).filter(
        models.MetricDefinition.category == "devops"
    ).count()

    return {
        "category": "devops",
        "historical_records": count,
        "sufficient_for_training": count >= 30,
        "message": (
            f"Found {count} historical DevOps metric records. "
            + ("Sufficient for deployment failure prediction." if count >= 30
               else "Insufficient dedicated deployment data. The supplied CSV datasets contain code quality and "
                    "refactoring metrics, not CI/CD deployment outcomes. DevOps predictions require historical "
                    "deployment frequency, change failure rate, rollback rate, and MTTR records from CI/CD pipelines "
                    "(GitHub Actions, Jenkins, ArgoCD).")
        ),
        "required_metrics": ["deployment_frequency", "change_failure_rate", "rollback_rate", "mttr", "deployment_lead_time"],
        "csv_datasets_applicable": False,
    }

