"""
predictions/services/model_evaluation.py

Model Evaluation Suite for Stage 5: AI Weather Prediction Models.

Calculates standard meteorological and statistical regression metrics:
  - MAE  (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - R²   (Coefficient of Determination)
  - MBE  (Mean Bias Error)
  - Corr (Pearson Correlation Coefficient)
"""
import numpy as np
from typing import Dict, Any, Union
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class ModelEvaluator:
    """Computes comparative evaluation metrics between model predictions and observations."""

    @staticmethod
    def calculate_metrics(y_true: Union[np.ndarray, list], y_pred: Union[np.ndarray, list]) -> Dict[str, float]:
        """
        Calculates MAE, RMSE, R², MBE, and Pearson correlation.
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        # Filter out any NaN pairs
        valid_mask = (~np.isnan(y_t)) & (~np.isnan(y_p))
        y_t = y_t[valid_mask]
        y_p = y_p[valid_mask]

        if len(y_t) == 0:
            return {
                'mae': 0.0,
                'rmse': 0.0,
                'r2': 0.0,
                'mbe': 0.0,
                'correlation': 0.0,
                'sample_count': 0,
            }

        mae = float(mean_absolute_error(y_t, y_p))
        rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))

        # R² score: can be negative if model performs worse than mean
        try:
            r2 = float(r2_score(y_t, y_p))
        except Exception:
            r2 = 0.0

        # Mean Bias Error (MBE = mean(y_pred - y_true))
        mbe = float(np.mean(y_p - y_t))

        # Pearson Correlation
        if np.std(y_t) > 1e-6 and np.std(y_p) > 1e-6:
            corr = float(np.corrcoef(y_t, y_p)[0, 1])
            if np.isnan(corr):
                corr = 0.0
        else:
            corr = 0.0

        return {
            'mae': round(mae, 4),
            'rmse': round(rmse, 4),
            'r2': round(r2, 4),
            'mbe': round(mbe, 4),
            'correlation': round(corr, 4),
            'sample_count': int(len(y_t)),
        }

    @classmethod
    def compare_models(
        cls,
        y_true: np.ndarray,
        baseline_pred: np.ndarray,
        ml_pred: np.ndarray,
        target_name: str = 'temperature'
    ) -> Dict[str, Any]:
        """
        Produces a comparative evaluation report distinguishing Baseline vs ML Model.
        """
        baseline_metrics = cls.calculate_metrics(y_true, baseline_pred)
        ml_metrics = cls.calculate_metrics(y_true, ml_pred)

        # Compute percentage improvement in MAE
        b_mae = baseline_metrics['mae']
        m_mae = ml_metrics['mae']
        mae_improvement_pct = 0.0
        if b_mae > 1e-6:
            mae_improvement_pct = round(((b_mae - m_mae) / b_mae) * 100.0, 2)

        return {
            'target': target_name,
            'baseline': baseline_metrics,
            'ml_model': ml_metrics,
            'mae_improvement_pct': mae_improvement_pct,
            'sample_count': baseline_metrics['sample_count'],
        }
