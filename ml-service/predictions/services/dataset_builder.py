"""
predictions/services/dataset_builder.py

Dataset builder for Stage 5 AI Weather Prediction Models.

Responsibilities:
  1. Reads historical weather records from database (forecast_type='HISTORICAL').
  2. Integrates soil moisture observations where available.
  3. Sorts chronologically.
  4. Delegates to WeatherFeatureEngineer for lag, rolling, and temporal features.
  5. Drops warmup rows where initial lag cannot be computed.
  6. Executes strict chronological train / validation / test split (70% / 15% / 15%).
  7. Formats reproducible datasets for ML training and evaluation without data leakage.
"""
import logging
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from django.utils import timezone

from weather.models import Weather
from soil.models import SoilMoisture
from farms.models import Farm
from .feature_engineering import WeatherFeatureEngineer

logger = logging.getLogger(__name__)


class PredictionDatasetBuilder:
    """Builds clean, chronologically-split training datasets from historical observations."""

    DEFAULT_TRAIN_RATIO = 0.70
    DEFAULT_VAL_RATIO = 0.15
    DEFAULT_TEST_RATIO = 0.15
    MINIMUM_SAMPLES_REQUIRED = 50

    def __init__(
        self,
        farm_id: Optional[int] = None,
        resolution: str = 'hourly',
        train_ratio: float = DEFAULT_TRAIN_RATIO,
        val_ratio: float = DEFAULT_VAL_RATIO,
        test_ratio: float = DEFAULT_TEST_RATIO,
    ):
        self.farm_id = farm_id
        self.resolution = resolution
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.feature_engineer = WeatherFeatureEngineer(resolution=resolution)

    def load_historical_dataframe(self) -> pd.DataFrame:
        """
        Loads historical weather records from Weather model into a pandas DataFrame.
        Optionally joins soil moisture observations.
        """
        qs = Weather.objects.filter(forecast_type='HISTORICAL')
        if self.farm_id:
            qs = qs.filter(farm_id=self.farm_id)

        qs = qs.order_by('timestamp')

        values = qs.values(
            'id', 'farm_id', 'timestamp', 'temperature', 'precipitation',
            'relative_humidity', 'wind_speed', 'evapotranspiration',
            'surface_pressure'
        )
        records = list(values)
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Merge farm coordinates if single farm
        if self.farm_id:
            try:
                farm = Farm.objects.get(id=self.farm_id)
                df['latitude'] = float(farm.latitude)
                df['longitude'] = float(farm.longitude)
            except Farm.DoesNotExist:
                df['latitude'] = 0.0
                df['longitude'] = 0.0

            # Attach soil moisture if present
            sm_qs = SoilMoisture.objects.filter(farm_id=self.farm_id).order_by('timestamp').values('timestamp', 'moisture')
            if sm_qs.exists():
                sm_df = pd.DataFrame(list(sm_qs))
                sm_df['timestamp'] = pd.to_datetime(sm_df['timestamp'])
                sm_df = sm_df.rename(columns={'moisture': 'soil_moisture'})[['timestamp', 'soil_moisture']]
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = pd.merge_asof(
                    df.sort_values('timestamp'),
                    sm_df.sort_values('timestamp'),
                    on='timestamp',
                    direction='backward'
                )
                df['soil_moisture'] = df['soil_moisture'].ffill().bfill().fillna(0.0)
            else:
                df['soil_moisture'] = 0.0
        else:
            df['latitude'] = 0.0
            df['longitude'] = 0.0
            df['soil_moisture'] = 0.0

        return df

    def build_dataset(self) -> Dict[str, Any]:
        """
        Executes full dataset construction pipeline:
          Load -> Feature Engineering -> Chronological Split -> Metadata.
        """
        raw_df = self.load_historical_dataframe()
        if raw_df.empty or len(raw_df) < self.MINIMUM_SAMPLES_REQUIRED:
            raise ValueError(
                f"Insufficient historical data to build ML dataset. "
                f"Found {len(raw_df)} records, minimum required is {self.MINIMUM_SAMPLES_REQUIRED}."
            )

        # Feature engineering with lag, rolling, and temporal columns
        feat_df = self.feature_engineer.create_features(raw_df, drop_warmup=True)

        n = len(feat_df)
        if n < 20:
            raise ValueError(f"Insufficient samples remaining after feature engineering warmup. Remaining: {n}")

        # Chronological Train / Val / Test Split
        train_end_idx = int(n * self.train_ratio)
        val_end_idx = int(n * (self.train_ratio + self.val_ratio))

        # Ensure at least 1 sample in each split
        train_end_idx = max(train_end_idx, 1)
        val_end_idx = max(val_end_idx, train_end_idx + 1)
        val_end_idx = min(val_end_idx, n - 1)

        train_df = feat_df.iloc[:train_end_idx].copy().reset_index(drop=True)
        val_df = feat_df.iloc[train_end_idx:val_end_idx].copy().reset_index(drop=True)
        test_df = feat_df.iloc[val_end_idx:].copy().reset_index(drop=True)

        metadata = {
            'total_samples': n,
            'train_samples': len(train_df),
            'val_samples': len(val_df),
            'test_samples': len(test_df),
            'train_start': train_df['timestamp'].min().isoformat(),
            'train_end': train_df['timestamp'].max().isoformat(),
            'val_start': val_df['timestamp'].min().isoformat(),
            'val_end': val_df['timestamp'].max().isoformat(),
            'test_start': test_df['timestamp'].min().isoformat(),
            'test_end': test_df['timestamp'].max().isoformat(),
            'resolution': self.resolution,
            'farm_id': self.farm_id,
        }

        return {
            'train': train_df,
            'val': val_df,
            'test': test_df,
            'full': feat_df,
            'metadata': metadata,
        }

    def prepare_target_data(
        self,
        dataset: Dict[str, Any],
        target_name: str
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, List[str]]:
        """
        Extracts feature matrix X and target vector y for train, val, and test splits.
        """
        train_df = dataset['train']
        val_df = dataset['val']
        test_df = dataset['test']

        feature_cols = self.feature_engineer.get_feature_columns(train_df, target_col=target_name)

        X_train = train_df[feature_cols].fillna(0.0)
        y_train = train_df[target_name].fillna(0.0)

        X_val = val_df[feature_cols].fillna(0.0)
        y_val = val_df[target_name].fillna(0.0)

        X_test = test_df[feature_cols].fillna(0.0)
        y_test = test_df[target_name].fillna(0.0)

        return X_train, y_train, X_val, y_val, X_test, y_test, feature_cols
