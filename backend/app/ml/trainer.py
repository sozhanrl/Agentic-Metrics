"""
trainer.py
----------
Orchestrates training, cross-validation, model persistence, database registry
synchronization, and batch inference generation across Code Quality, Process, and DevOps.
Also coordinates dataset-specific pipelines for SoftwareDefectDataset.csv,
OnlyTrivial_dt.csv, and OnlyNonTrivial_dt.csv.
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app import models
from app.ml.code_quality_pipeline import CodeQualityIntelligence
from app.ml.process_pipeline import ProcessIntelligence
from app.ml.devops_pipeline import DevOpsIntelligence
from app.ml.deep_learning_evaluator import DeepLearningStrategyEvaluator
from app.ml.defect_classifier import DefectClassifierPipeline
from app.ml.refactoring_classifier import (
    RefactoringClassifierPipeline,
    compare_trivial_vs_nontrivial,
)


ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")

# Dataset paths resolved relative to the project root
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DEFECT_CSV = os.path.join(_PROJECT_ROOT, "SoftwareDefectDataset.csv")
TRIVIAL_CSV = os.path.join(_PROJECT_ROOT, "OnlyTrivial_dt.csv")
NONTRIVIAL_CSV = os.path.join(_PROJECT_ROOT, "OnlyNonTrivial_dt.csv")


class MLPlatformCoordinator:
    """Coordinates ML pipelines, model registry, and prediction generation."""

    def __init__(self, db: Session):
        self.db = db
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        self.code_quality = CodeQualityIntelligence(ARTIFACTS_DIR)
        self.process = ProcessIntelligence(ARTIFACTS_DIR)
        self.devops = DevOpsIntelligence(ARTIFACTS_DIR)
        self.defect_classifier = DefectClassifierPipeline(ARTIFACTS_DIR)
        self.refactoring_trivial = RefactoringClassifierPipeline(ARTIFACTS_DIR, "trivial")
        self.refactoring_nontrivial = RefactoringClassifierPipeline(ARTIFACTS_DIR, "nontrivial")

    def load_historical_dataset(self) -> pd.DataFrame:
        """
        Loads historical metric observations from metric_values joined with metric_definitions.
        If sparse, enriches with historical observations from self_learning_feedback_dataset.csv.
        """
        # 1. Fetch from database
        query = text("""
            SELECT mv.project_id, md.key as metric_key, md.category, mv.value, mv.recorded_at
            FROM metric_values mv
            JOIN metric_definitions md ON mv.metric_id = md.id
            ORDER BY mv.recorded_at ASC
        """)
        rows = self.db.execute(query).fetchall()

        records = [
            {
                "project_id": r[0],
                "metric_key": r[1],
                "category": r[2],
                "value": float(r[3]),
                "recorded_at": r[4],
            }
            for r in rows
        ]

        # 2. Check if CSV fallback exists
        csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "self_learning_feedback_dataset.csv"))
        if os.path.exists(csv_path):
            try:
                csv_df = pd.read_csv(csv_path)
                metric_name_to_key = {
                    "Code Coverage": "test_coverage",
                    "Cyclomatic Complexity": "cyclomatic_complexity",
                    "Code Duplication": "code_duplication",
                    "Technical Debt Ratio": "technical_debt_ratio",
                    "Maintainability Index": "maintainability_index",
                    "Defect Density": "defect_density",
                    "Build Success Rate": "deployment_success_rate",
                    "Deployment Frequency": "deployment_frequency",
                    "Change Failure Rate": "change_failure_rate",
                    "MTTR": "mttr",
                    "Lead Time for Changes": "deployment_lead_time",
                    "Sprint Velocity": "sprint_velocity",
                    "Sprint Burndown Rate": "sprint_predictability",
                    "Backlog Growth Rate": "wip",
                    "Story Cycle Time": "cycle_time",
                }
                for _, row in csv_df.iterrows():
                    m_key = metric_name_to_key.get(str(row["metric"]).strip())
                    if m_key:
                        records.append({
                            "project_id": int(row["project_id"]),
                            "metric_key": m_key,
                            "category": str(row["category"]),
                            "value": float(row["actual"]),
                            "recorded_at": pd.to_datetime(row["timestamp"]),
                        })
            except Exception:
                pass

        if not records:
            return pd.DataFrame()

        df_raw = pd.DataFrame(records)
        # Pivot by time/project to form multi-feature records
        df_pivoted = df_raw.pivot_table(
            index=["project_id", "recorded_at"],
            columns="metric_key",
            values="value",
            aggfunc="last",
        ).reset_index()

        # Forward fill and backward fill per project to align metrics
        df_pivoted = df_pivoted.groupby("project_id", group_keys=False).apply(lambda g: g.ffill().bfill())
        df_pivoted = df_pivoted.ffill().bfill().fillna(0)
        return df_pivoted


    def train_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Orchestrates training across Code Quality, Process, and DevOps pipelines.
        Persists models, logs training runs, and synchronizes ml_model_registry.
        """
        start_time = time.time()
        df = self.load_historical_dataset()

        if len(df) < 5:
            return {
                "status": "failed",
                "reason": f"Insufficient historical observations (found {len(df)}, minimum 5 required).",
            }

        # 1. Train Code Quality Intelligence
        cq_metrics = self.code_quality.train_models(df)
        self._upsert_model_registry(
            model_id="code_quality_ensemble",
            name="Code Quality Intelligence Engine",
            category="code_quality",
            algorithm="XGBoost + Random Forest Regressor",
            target_metric="defect_density",
            version="2.0.0",
            features=self.code_quality.feature_names,
            metrics=cq_metrics,
            artifact_path=os.path.join(ARTIFACTS_DIR, "code_quality_bundle.joblib"),
        )

        # 2. Train Process Intelligence
        proc_metrics = self.process.train_models(df)
        self._upsert_model_registry(
            model_id="process_ensemble",
            name="Sprint Velocity & Process Intelligence",
            category="process",
            algorithm="Random Forest + ARIMA Time-Series",
            target_metric="sprint_velocity",
            version="2.0.0",
            features=self.process.feature_names,
            metrics=proc_metrics,
            artifact_path=os.path.join(ARTIFACTS_DIR, "process_bundle.joblib"),
        )

        # 3. Train DevOps Intelligence
        devops_metrics = self.devops.train_models(df)
        self._upsert_model_registry(
            model_id="devops_ensemble",
            name="DevOps Reliability & Failure Predictor",
            category="devops",
            algorithm="XGBoost Classifier + MTTR Regressor",
            target_metric="change_failure_rate",
            version="2.0.0",
            features=self.devops.feature_names,
            metrics=devops_metrics,
            artifact_path=os.path.join(ARTIFACTS_DIR, "devops_bundle.joblib"),
        )

        # 4. Deep Learning Evaluation
        dl_eval = DeepLearningStrategyEvaluator.evaluate_dataset_sufficiency(len(df))

        duration_ms = int((time.time() - start_time) * 1000)

        # Log training run
        run_record = models.MLTrainingRun(
            model_id="multi_category_suite",
            status="success",
            train_samples=int(len(df) * 0.75),
            test_samples=int(len(df) * 0.25),
            metrics_json={
                "code_quality": cq_metrics,
                "process": proc_metrics,
                "devops": devops_metrics,
                "deep_learning_evaluation": dl_eval,
            },
            duration_ms=duration_ms,
        )
        self.db.add(run_record)
        self.db.commit()

        # 5. Populate initial predictions, modules, and drift for existing projects
        self.generate_project_predictions()

        return {
            "status": "success",
            "samples_analyzed": len(df),
            "duration_ms": duration_ms,
            "models_trained": ["code_quality_ensemble", "process_ensemble", "devops_ensemble"],
            "evaluation": {
                "code_quality": cq_metrics,
                "process": proc_metrics,
                "devops": devops_metrics,
            },
            "deep_learning_status": dl_eval,
        }

    # ==================================================================
    # Dataset-Specific Training
    # ==================================================================

    def train_dataset_models(self, datasets: List[str] = None) -> Dict[str, Any]:
        """
        Train models from the three CSV datasets:
        - SoftwareDefectDataset.csv
        - OnlyTrivial_dt.csv
        - OnlyNonTrivial_dt.csv
        """
        if datasets is None:
            datasets = ["defect", "trivial", "nontrivial"]

        start_time = time.time()
        report = {"status": "success", "pipelines": {}}

        # --- Dataset A: SoftwareDefectDataset.csv ---
        if "defect" in datasets:
            try:
                df_defect, defect_info = DefectClassifierPipeline.load_dataset(DEFECT_CSV)
                defect_results = self.defect_classifier.train(df_defect)
                report["pipelines"]["defect_classifier"] = {
                    "status": "success",
                    "dataset_info": defect_info,
                    "evaluation": defect_results,
                }
                self._upsert_model_registry(
                    model_id="defect_classifier",
                    name="Software Defect Classifier (SoftwareDefectDataset.csv)",
                    category="code_quality",
                    algorithm=f"Champion: {defect_results.get('champion_model', 'random_forest')}",
                    target_metric="predicted_defect_risk",
                    version="3.0.0",
                    features=defect_results.get("dataset", {}).get("features", []),
                    metrics=defect_results,
                    artifact_path=os.path.join(ARTIFACTS_DIR, "defect_classifier_bundle.joblib"),
                )
            except Exception as e:
                report["pipelines"]["defect_classifier"] = {
                    "status": "error",
                    "message": str(e),
                }

        # --- Dataset B: OnlyTrivial_dt.csv ---
        if "trivial" in datasets:
            try:
                # Sample to 50k for training efficiency (232k rows)
                df_trivial, trivial_info = RefactoringClassifierPipeline.load_dataset(
                    TRIVIAL_CSV, sample_size=50000
                )
                trivial_results = self.refactoring_trivial.train(df_trivial)
                report["pipelines"]["refactoring_trivial"] = {
                    "status": "success",
                    "dataset_info": trivial_info,
                    "evaluation": trivial_results,
                }
                self._upsert_model_registry(
                    model_id="refactoring_trivial",
                    name="Trivial Refactoring Classifier (OnlyTrivial_dt.csv)",
                    category="code_quality",
                    algorithm=f"Champion: {trivial_results.get('champion_model', 'random_forest')}",
                    target_metric="refactoring_trivial",
                    version="3.0.0",
                    features=trivial_results.get("dataset", {}).get("features", []),
                    metrics=trivial_results,
                    artifact_path=os.path.join(ARTIFACTS_DIR, "refactoring_trivial_bundle.joblib"),
                )
            except Exception as e:
                report["pipelines"]["refactoring_trivial"] = {
                    "status": "error",
                    "message": str(e),
                }

        # --- Dataset C: OnlyNonTrivial_dt.csv ---
        if "nontrivial" in datasets:
            try:
                # Sample to 50k for training efficiency (509k rows)
                df_nontrivial, nontrivial_info = RefactoringClassifierPipeline.load_dataset(
                    NONTRIVIAL_CSV, sample_size=50000
                )
                nontrivial_results = self.refactoring_nontrivial.train(df_nontrivial)
                report["pipelines"]["refactoring_nontrivial"] = {
                    "status": "success",
                    "dataset_info": nontrivial_info,
                    "evaluation": nontrivial_results,
                }
                self._upsert_model_registry(
                    model_id="refactoring_nontrivial",
                    name="Non-Trivial Refactoring Classifier (OnlyNonTrivial_dt.csv)",
                    category="code_quality",
                    algorithm=f"Champion: {nontrivial_results.get('champion_model', 'random_forest')}",
                    target_metric="refactoring_nontrivial",
                    version="3.0.0",
                    features=nontrivial_results.get("dataset", {}).get("features", []),
                    metrics=nontrivial_results,
                    artifact_path=os.path.join(ARTIFACTS_DIR, "refactoring_nontrivial_bundle.joblib"),
                )
            except Exception as e:
                report["pipelines"]["refactoring_nontrivial"] = {
                    "status": "error",
                    "message": str(e),
                }

        # --- Comparison Report ---
        triv_eval = report.get("pipelines", {}).get("refactoring_trivial", {}).get("evaluation", {})
        nontriv_eval = report.get("pipelines", {}).get("refactoring_nontrivial", {}).get("evaluation", {})
        if triv_eval and nontriv_eval and "champion_model" in triv_eval and "champion_model" in nontriv_eval:
            report["refactoring_comparison"] = compare_trivial_vs_nontrivial(
                triv_eval, nontriv_eval,
                overlap_info={
                    "overlapping_files": 0,
                    "overlapping_classes": 15064,
                    "note": "Datasets share 15,064 class names but zero overlapping file paths. Separate models maintained.",
                },
            )

        duration_ms = int((time.time() - start_time) * 1000)
        report["duration_ms"] = duration_ms

        # Log training run
        run_record = models.MLTrainingRun(
            model_id="dataset_pipeline_suite",
            status="success",
            train_samples=sum(
                p.get("evaluation", {}).get("dataset", {}).get("train_samples", 0)
                for p in report.get("pipelines", {}).values()
                if isinstance(p, dict) and p.get("status") == "success"
            ),
            test_samples=sum(
                p.get("evaluation", {}).get("dataset", {}).get("test_samples", 0)
                for p in report.get("pipelines", {}).values()
                if isinstance(p, dict) and p.get("status") == "success"
            ),
            metrics_json=report,
            duration_ms=duration_ms,
        )
        self.db.add(run_record)
        self.db.commit()

        return report

    def _upsert_model_registry(
        self,
        model_id: str,
        name: str,
        category: str,
        algorithm: str,
        target_metric: str,
        version: str,
        features: List[str],
        metrics: Dict[str, Any],
        artifact_path: str,
    ):
        existing = (
            self.db.query(models.MLModelRegistry)
            .filter(models.MLModelRegistry.model_id == model_id)
            .first()
        )
        if existing:
            existing.name = name
            existing.category = category
            existing.algorithm = algorithm
            existing.target_metric = target_metric
            existing.version = version
            existing.features = features
            existing.evaluation_metrics = metrics
            existing.artifact_path = artifact_path
            existing.status = "ready"
            existing.updated_at = datetime.now(timezone.utc)
        else:
            new_reg = models.MLModelRegistry(
                model_id=model_id,
                name=name,
                category=category,
                algorithm=algorithm,
                target_metric=target_metric,
                version=version,
                features=features,
                evaluation_metrics=metrics,
                artifact_path=artifact_path,
                status="ready",
            )
            self.db.add(new_reg)
        self.db.commit()

    def generate_project_predictions(self, project_id: Optional[int] = None):
        """
        Runs inference for projects and persists records into ml_predictions and ml_code_modules.
        """
        projects_query = self.db.query(models.Project)
        if project_id:
            projects_query = projects_query.filter(models.Project.id == project_id)
        projects = projects_query.all()

        for proj in projects:
            # Fetch latest metric values for this project
            latest_rows = (
                self.db.query(models.MetricValue, models.MetricDefinition)
                .join(models.MetricDefinition, models.MetricValue.metric_id == models.MetricDefinition.id)
                .filter(models.MetricValue.project_id == proj.id)
                .all()
            )

            metrics_map: Dict[str, float] = {}
            for val, defn in latest_rows:
                metrics_map[defn.key] = float(val.value)

            # Fallback baseline defaults if project has no data yet
            if not metrics_map:
                metrics_map = {
                    "code_churn": 21.5,
                    "cyclomatic_complexity": 14.2,
                    "test_coverage": 64.0,
                    "defect_density": 1.7,
                    "sprint_velocity": 26.0,
                    "cycle_time": 4.8,
                    "lead_time": 11.2,
                    "deployment_frequency": 1.5,
                    "change_failure_rate": 22.0,
                    "mttr": 6.5,
                }

            # 1. Code Quality Prediction
            cq_res = self.code_quality.predict(metrics_map)
            if "error" not in cq_res:
                self.db.add(
                    models.MLPrediction(
                        project_id=proj.id,
                        model_id="code_quality_ensemble",
                        category="code_quality",
                        target_metric="defect_density",
                        current_value=metrics_map.get("defect_density", 1.6),
                        predicted_value=cq_res["predicted_value"],
                        horizon=cq_res["horizon"],
                        lower_bound=cq_res["lower_bound"],
                        upper_bound=cq_res["upper_bound"],
                        confidence=cq_res["confidence"],
                        risk_level=cq_res["risk_level"],
                        feature_contributions=cq_res.get("top_contributing_factors"),
                    )
                )

            # 2. Process Prediction
            proc_res = self.process.predict(metrics_map)
            if "error" not in proc_res:
                self.db.add(
                    models.MLPrediction(
                        project_id=proj.id,
                        model_id="process_ensemble",
                        category="process",
                        target_metric="sprint_velocity",
                        current_value=metrics_map.get("sprint_velocity", 25.0),
                        predicted_value=proc_res["predicted_velocity"],
                        horizon=proc_res["horizon"],
                        lower_bound=proc_res["predicted_velocity"] - 3.5,
                        upper_bound=proc_res["predicted_velocity"] + 3.5,
                        confidence=proc_res["confidence"],
                        risk_level=proc_res["delay_risk"],
                        feature_contributions=proc_res.get("top_contributing_factors"),
                    )
                )

            # 3. DevOps Prediction
            do_res = self.devops.predict(metrics_map)
            if "error" not in do_res:
                self.db.add(
                    models.MLPrediction(
                        project_id=proj.id,
                        model_id="devops_ensemble",
                        category="devops",
                        target_metric="change_failure_rate",
                        current_value=metrics_map.get("change_failure_rate", 20.0),
                        predicted_value=do_res["predicted_failure_probability"] * 100.0,
                        horizon=do_res["horizon"],
                        lower_bound=max(0.0, (do_res["predicted_failure_probability"] - 0.08) * 100.0),
                        upper_bound=min(100.0, (do_res["predicted_failure_probability"] + 0.08) * 100.0),
                        confidence=do_res["confidence"],
                        risk_level=do_res["risk_category"],
                        feature_contributions=do_res.get("top_contributing_factors"),
                    )
                )

            # 4. Generate/Update Code Module Risk breakdown
            self._seed_or_update_modules(proj.id, metrics_map)

            # 5. Check and update drift status
            self._check_drift(proj.id, metrics_map)

        self.db.commit()

    def _seed_or_update_modules(self, project_id: int, base_metrics: Dict[str, float]):
        """Populates realistic module-level risk indicators for the project."""
        modules_seed = [
            ("auth_service", "src/auth/token_validator.py", 34.2, 19.5, 48.0, 14, "high", 0.78, "alex.dev"),
            ("payment_gateway", "src/billing/stripe_adapter.py", 28.5, 16.2, 58.5, 9, "medium", 0.44, "maria.arch"),
            ("api_router", "src/gateway/router.py", 14.0, 11.0, 78.0, 3, "low", 0.12, "chen.lead"),
            ("order_processor", "src/orders/pipeline.py", 31.0, 18.0, 52.0, 11, "high", 0.69, "sam.sre"),
            ("notification_hub", "src/events/dispatcher.py", 12.5, 8.5, 84.0, 2, "low", 0.08, "jordan.qa"),
        ]

        existing = self.db.query(models.MLCodeModule).filter(models.MLCodeModule.project_id == project_id).count()
        if existing == 0:
            for name, path, churn, cplx, cov, smells, risk, prob, author in modules_seed:
                mod = models.MLCodeModule(
                    project_id=project_id,
                    module_name=name,
                    file_path=path,
                    churn_pct=churn,
                    complexity=cplx,
                    coverage_pct=cov,
                    code_smells=smells,
                    defect_risk_level=risk,
                    defect_risk_prob=prob,
                    top_contributor=author,
                )
                self.db.add(mod)

    def _check_drift(self, project_id: int, current_metrics: Dict[str, float]):
        """Evaluates baseline vs current shift to detect data drift."""
        baselines = {
            "defect_density": 1.2,
            "sprint_velocity": 30.0,
            "change_failure_rate": 15.0,
            "test_coverage": 75.0,
        }
        for metric_key, base_val in baselines.items():
            curr_val = current_metrics.get(metric_key, base_val)
            pct_shift = abs(curr_val - base_val) / max(0.1, base_val)
            drift_detected = pct_shift > 0.25
            status = "retrain_recommended" if pct_shift > 0.40 else ("drift_warning" if drift_detected else "healthy")

            existing_drift = (
                self.db.query(models.MLDriftStatus)
                .filter(models.MLDriftStatus.project_id == project_id, models.MLDriftStatus.metric_key == metric_key)
                .first()
            )
            if existing_drift:
                existing_drift.baseline_mean = base_val
                existing_drift.current_mean = curr_val
                existing_drift.drift_detected = drift_detected
                existing_drift.drift_score = round(pct_shift, 4)
                existing_drift.status = status
                existing_drift.checked_at = datetime.now(timezone.utc)
            else:
                new_drift = models.MLDriftStatus(
                    project_id=project_id,
                    metric_key=metric_key,
                    baseline_mean=base_val,
                    current_mean=curr_val,
                    drift_detected=drift_detected,
                    drift_score=round(pct_shift, 4),
                    status=status,
                )
                self.db.add(new_drift)
