"""
predictions/services/baseline_model.py

Baseline model implementation for Stage 5: AI Weather Prediction Models.

Implements Persistence (Last-Value) Baseline:
  y_hat(t) = y(t - 1)
  
Serves as the empirical benchmark to quantify whether machine learning
regressors demonstrate measurable improvement over naive persistence.
"""
import numpy as np
import pandas as pd
from typing import Union


class PersistenceBaselineModel:
    """
    Persistence / Last-Value Baseline Predictor.
    
    Predicts that future weather will equal the most recently observed value:
        y_hat[t] = y[t - 1]
    """

    def __init__(self, target_variable: str):
        """
        :param target_variable: e.g. 'temperature', 'precipitation', 'relative_humidity', 'wind_speed'
        """
        self.target_variable = target_variable
        self.lag_feature_name = f"{target_variable}_lag_1"
        self._last_train_mean = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]):
        """
        Fits baseline. For persistence, this captures the mean fallback value if lag is missing.
        """
        if isinstance(y, pd.Series):
            self._last_train_mean = float(y.mean())
        elif isinstance(y, np.ndarray):
            self._last_train_mean = float(np.nanmean(y))
        else:
            self._last_train_mean = 0.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Generates persistence predictions by extracting the lag-1 feature column.
        
        :param X: DataFrame containing features, including f'{target_variable}_lag_1'
        :return: np.ndarray of baseline predictions
        """
        if isinstance(X, pd.DataFrame) and self.lag_feature_name in X.columns:
            preds = X[self.lag_feature_name].to_numpy(dtype=float)
            # Handle any residual NaNs with last known mean
            if np.isnan(preds).any():
                fallback = self._last_train_mean if self._last_train_mean is not None else 0.0
                preds = np.nan_to_num(preds, nan=fallback)
            return preds

        # Fallback if DataFrame does not have the named lag column
        if self._last_train_mean is not None:
            return np.full(shape=(len(X),), fill_value=self._last_train_mean)
        return np.zeros(shape=(len(X),))
