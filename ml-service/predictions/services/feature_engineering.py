"""
predictions/services/feature_engineering.py

Feature engineering pipeline for Stage 5 AI Weather Prediction Models.

Features constructed:
  1. Temporal features:
     - hour, day, day_of_week, day_of_year, month
     - cyclical sine/cosine transformations for hour and month
  2. Lag features:
     - Previous 1h, 2h, 3h, 24h for temperature, precipitation, relative_humidity, wind_speed
     (or 1d, 2d, 3d, 7d if daily resolution)
  3. Rolling features (strictly shifted to prevent data leakage):
     - 3h, 6h, 24h rolling means
     - 24h cumulative precipitation
  4. Environmental & spatial features:
     - evapotranspiration, surface_pressure, latitude, longitude, soil_moisture (if present)

PREVENTS DATA LEAKAGE:
  - All lags and rolling calculations use observations strictly prior to the target time (t).
  - Shifted rolling windows ensure y(t) is never leaked into X(t).
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class WeatherFeatureEngineer:
    """Transforms chronological weather observations into engineered feature matrices."""

    CORE_TARGETS = ['temperature', 'precipitation', 'relative_humidity', 'wind_speed']

    def __init__(self, resolution: str = 'hourly'):
        """
        :param resolution: 'hourly' or 'daily'
        """
        self.resolution = resolution

    def create_features(self, df: pd.DataFrame, drop_warmup: bool = True) -> pd.DataFrame:
        """
        Takes a DataFrame with columns:
          timestamp (datetime), temperature, precipitation, relative_humidity, wind_speed,
          and optional: evapotranspiration, surface_pressure, soil_moisture, latitude, longitude.
        
        Returns a new DataFrame with all engineered temporal, lag, rolling, and environmental features.
        """
        if df.empty:
            return df

        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Ensure strict chronological sorting
        df = df.sort_values('timestamp').reset_index(drop=True)

        # 1. TEMPORAL FEATURES
        ts = df['timestamp'].dt
        df['hour'] = ts.hour
        df['day'] = ts.day
        df['day_of_week'] = ts.dayofweek
        df['day_of_year'] = ts.dayofyear
        df['month'] = ts.month

        # Cyclical transformations (smooth continuous periodicity)
        df['sin_hour'] = np.sin(2 * np.pi * df['hour'] / 24.0)
        df['cos_hour'] = np.cos(2 * np.pi * df['hour'] / 24.0)
        df['sin_month'] = np.sin(2 * np.pi * (df['month'] - 1) / 12.0)
        df['cos_month'] = np.cos(2 * np.pi * (df['month'] - 1) / 12.0)

        # 2. LAG FEATURES
        # For hourly data: 1h, 2h, 3h, 24h lags
        # For daily data: 1d, 2d, 3d, 7d lags
        lag_steps = [1, 2, 3, 24] if self.resolution == 'hourly' else [1, 2, 3, 7]

        for col in self.CORE_TARGETS:
            if col in df.columns:
                for lag in lag_steps:
                    df[f'{col}_lag_{lag}'] = df[col].shift(lag)

        # 3. ROLLING WINDOW FEATURES (Strictly Shifted by 1 step to prevent leakage)
        # rolling windows on past observations: window_size steps before the target
        rolling_windows = [3, 6, 24] if self.resolution == 'hourly' else [3, 7]

        for col in self.CORE_TARGETS:
            if col in df.columns:
                for w in rolling_windows:
                    # shift(1) guarantees current step's value is excluded from rolling average
                    df[f'{col}_rolling_mean_{w}'] = df[col].shift(1).rolling(window=w, min_periods=w).mean()

        # Cumulative precipitation (e.g. 24h past total rainfall)
        if 'precipitation' in df.columns:
            cum_win = 24 if self.resolution == 'hourly' else 7
            df[f'precip_cum_{cum_win}'] = df['precipitation'].shift(1).rolling(window=cum_win, min_periods=cum_win).sum()

        # 4. ENVIRONMENTAL & STATIC FEATURES
        # Ensure spatial features exist
        if 'latitude' not in df.columns:
            df['latitude'] = 0.0
        if 'longitude' not in df.columns:
            df['longitude'] = 0.0

        if 'evapotranspiration' in df.columns:
            df['et_lag_1'] = df['evapotranspiration'].shift(1)
            df['et_lag_24'] = df['evapotranspiration'].shift(24 if self.resolution == 'hourly' else 7)
        if 'surface_pressure' in df.columns:
            df['pressure_lag_1'] = df['surface_pressure'].shift(1)

        # Fill small gaps in environmental features if present
        for env_col in ['soil_moisture', 'evapotranspiration', 'surface_pressure']:
            if env_col in df.columns:
                df[env_col] = df[env_col].ffill().bfill().fillna(0.0)

        # 5. DROP WARMUP ROWS (initial rows where lags cannot be computed)
        if drop_warmup:
            max_lag = max(lag_steps)
            df = df.iloc[max_lag:].reset_index(drop=True)

        return df

    def get_feature_columns(self, df: pd.DataFrame, target_col: str) -> List[str]:
        """
        Returns list of feature column names suitable for predicting target_col.
        Excludes timestamp, id, farm_id, and any raw future target columns.
        """
        exclude = {
            'id', 'farm_id', 'farm', 'timestamp', 'created_at', 'updated_at',
            'forecast_type', 'source', 'weather_code', 'apparent_temperature',
            'precipitation_probability', 'rain'
        }
        # Also exclude raw target columns (y)
        exclude.update(self.CORE_TARGETS)

        features = [c for c in df.columns if c not in exclude and not c.startswith('target_')]
        return sorted(features)
