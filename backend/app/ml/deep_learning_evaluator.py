"""
deep_learning_evaluator.py
--------------------------
Evaluates the viability of Deep Learning (LSTM / Sequence Models / MLPs) against
tree-based baselines as mandated by Section 4:
"Do not add Deep Learning simply for appearance. First implement and evaluate
the ML baselines. For small tabular datasets, prefer tree-based models over
deep neural networks. Display the selected model and explain why it was selected.
If the data is insufficient, show that Deep Learning is unavailable due to
insufficient training data rather than producing misleading predictions."
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler


class DeepLearningStrategyEvaluator:
    """Evaluates whether deep learning is statistically justified or should be deactivated."""

    MIN_SAMPLES_FOR_RECURRENT_DL = 250

    @classmethod
    def evaluate_dataset_sufficiency(cls, n_samples: int) -> Dict[str, Any]:
        """
        Assesses sample count against statistical requirements for deep learning sequence models.
        """
        if n_samples < cls.MIN_SAMPLES_FOR_RECURRENT_DL:
            return {
                "dl_available": False,
                "status": "Inactive (Insufficient Training Data)",
                "sample_count": n_samples,
                "threshold_required": cls.MIN_SAMPLES_FOR_RECURRENT_DL,
                "selected_paradigm": "Tree-Based Ensemble (XGBoost + Random Forest)",
                "technical_justification": (
                    f"Available sequential observations (N={n_samples}) are below the minimum threshold "
                    f"(N >= {cls.MIN_SAMPLES_FOR_RECURRENT_DL}) required for recurrent sequence models (LSTM/GRU) "
                    "to converge without severe parameter overfitting. Tree-based ensembles exhibit higher sample efficiency, "
                    "exact feature attribution, and lower generalization error on tabular software metrics."
                ),
                "model_comparison": {
                    "xgboost_mae_advantage": "Superior sample efficiency on tabular software metrics",
                    "lstm_feasibility": "Requires continuous long-term historical time-series (>250 sprints/deployments)",
                },
            }

        return {
            "dl_available": True,
            "status": "Active / Evaluated",
            "sample_count": n_samples,
            "selected_paradigm": "Hybrid Tree-Ensemble & Neural Sequence Model",
            "technical_justification": "Sufficient sequential records exist to support neural sequence benchmarking.",
        }

    @classmethod
    def benchmark_shallow_neural_net(
        cls, X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray, y_test: np.ndarray, tree_mae: float
    ) -> Dict[str, Any]:
        """
        Trains an MLP neural network baseline to test whether deep representations
        outperform tree-based ensembles on the current dataset.
        """
        try:
            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)

            mlp = MLPRegressor(
                hidden_layer_sizes=(32, 16),
                activation="relu",
                max_iter=300,
                random_state=42,
                early_stopping=True,
            )
            mlp.fit(X_train_s, y_train)
            preds = mlp.predict(X_test_s)
            mlp_mae = float(mean_absolute_error(y_test, preds))
            mlp_rmse = float(np.sqrt(mean_squared_error(y_test, preds)))

            tree_wins = tree_mae <= mlp_mae
            selected = "Tree-Based Ensemble (XGBoost / Random Forest)" if tree_wins else "Neural Network (MLP)"

            return {
                "neural_net_mae": round(mlp_mae, 4),
                "neural_net_rmse": round(mlp_rmse, 4),
                "tree_ensemble_mae": round(tree_mae, 4),
                "winner": selected,
                "reason": (
                    "Tree ensemble outperformed Neural Network due to tabular feature boundaries and limited sample size."
                    if tree_wins
                    else "Neural network captured continuous nonlinear interactions with lower validation error."
                ),
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "winner": "Tree-Based Ensemble (XGBoost / Random Forest)",
                "reason": "Tree ensemble selected by default.",
            }
