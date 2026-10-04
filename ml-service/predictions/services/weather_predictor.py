"""
predictions/services/weather_predictor.py

Inference service for Stage 5: AI Weather Prediction Models.

Loads trained scikit-learn models and generates multi-step 24-hour ahead predictions
using real farm historical & current observations.
"""
import os
import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib
from django.utils import timezone
from django.conf import settings

from farms.models import Farm
from weather.models import Weather
from soil.models import SoilMoisture
from predictions.models import WeatherPrediction, ModelMetadata
from .feature_engineering import WeatherFeatureEngineer

logger = logging.getLogger(__name__)


class ModelNotTrainedError(Exception):
    """Raised when active model artifacts are not found in the database or filesystem."""
    pass


class InsufficientDataError(Exception):
    """Raised when there is not enough recent observation data to construct features."""
    pass


class WeatherPredictionService:
    """Performs inference using trained scikit-learn Random Forest weather models."""

    CORE_TARGETS = ['temperature', 'precipitation', 'relative_humidity', 'wind_speed']

    def __init__(self, farm: Farm):
        self.farm = farm
        self.feature_engineer = WeatherFeatureEngineer(resolution='hourly')

    def get_active_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads active model artifacts for each weather target.
        Prefers farm-specific active models, falls back to global models.
        """
        loaded_models = {}

        for target in self.CORE_TARGETS:
            meta = (
                ModelMetadata.objects.filter(farm=self.farm, target=target, is_active=True).first()
                or ModelMetadata.objects.filter(farm__isnull=True, target=target, is_active=True).first()
            )

            if not meta:
                continue

            if not meta.artifact_path or not os.path.exists(meta.artifact_path):
                logger.warning(f"Model artifact file missing for {target}: {meta.artifact_path}")
                continue

            try:
                payload = joblib.load(meta.artifact_path)
                loaded_models[target] = {
                    'model': payload['model'],
                    'features': payload['features'],
                    'version': meta.version,
                    'metadata': meta,
                }
            except Exception as e:
                logger.error(f"Failed to load artifact {meta.artifact_path}: {e}")

        if not loaded_models:
            raise ModelNotTrainedError(
                f"No trained AI weather model available for farm {self.farm.id} ({self.farm.farm_name}). "
                "Please run 'python manage.py train_weather_models' first."
            )

        return loaded_models

    def predict_24h(self, persist: bool = True) -> Dict[str, Any]:
        """
        Generates 24-hour ahead hourly weather predictions.
        
        Uses recent historical/current observations to seed lag and rolling features,
        then rolls forward autoregressively for 24 steps.
        """
        active_models = self.get_active_models()

        # Load recent observations (at least 48 hours for reliable 24h lags & rolling means)
        recent_records = Weather.objects.filter(
            farm=self.farm
        ).order_by('-timestamp')[:72]

        if not recent_records.exists() or len(recent_records) < 24:
            raise InsufficientDataError(
                f"Farm {self.farm.id} has only {len(recent_records)} observation records. "
                "At least 24 hourly records are required to seed feature lags."
            )

        # Reverse to chronological order
        records_list = list(reversed(list(recent_records)))
        df_obs = pd.DataFrame([{
            'timestamp': r.timestamp,
            'temperature': r.temperature,
            'precipitation': r.precipitation or 0.0,
            'relative_humidity': r.relative_humidity,
            'wind_speed': r.wind_speed,
            'evapotranspiration': r.evapotranspiration or 0.0,
            'surface_pressure': r.surface_pressure or 1013.25,
            'latitude': float(self.farm.latitude),
            'longitude': float(self.farm.longitude),
        } for r in records_list])

        # Get latest soil moisture if available
        sm_last = SoilMoisture.objects.filter(farm=self.farm).order_by('-timestamp').first()
        df_obs['soil_moisture'] = float(sm_last.moisture) if sm_last else 0.0

        current_time = timezone.now()
        last_obs_time = df_obs['timestamp'].iloc[-1]
        sim_df = df_obs.copy()

        horizon_hours = 24
        predictions_output: List[Dict[str, Any]] = []
        model_version_used = list(active_models.values())[0]['version']

        # Iteratively predict each future hour
        for step in range(1, horizon_hours + 1):
            next_timestamp = last_obs_time + timedelta(hours=step)

            # Build feature row for next_timestamp
            temp_row = {
                'timestamp': next_timestamp,
                'temperature': np.nan,
                'precipitation': np.nan,
                'relative_humidity': np.nan,
                'wind_speed': np.nan,
                'evapotranspiration': sim_df['evapotranspiration'].iloc[-1],
                'surface_pressure': sim_df['surface_pressure'].iloc[-1],
                'soil_moisture': sim_df['soil_moisture'].iloc[-1],
                'latitude': float(self.farm.latitude),
                'longitude': float(self.farm.longitude),
            }

            candidate_df = pd.concat([sim_df, pd.DataFrame([temp_row])], ignore_index=True)
            # Create lag and rolling features on candidate_df
            feat_df = self.feature_engineer.create_features(candidate_df, drop_warmup=False)
            target_row_features = feat_df.iloc[-1]

            step_preds: Dict[str, float] = {}

            # Predict each target
            for target_name in self.CORE_TARGETS:
                if target_name in active_models:
                    model_info = active_models[target_name]
                    model = model_info['model']
                    features = model_info['features']

                    # Extract required feature vector
                    x_vec = pd.DataFrame([target_row_features[features].fillna(0.0)])
                    pred_val = float(model.predict(x_vec)[0])

                    # Physical bounds clamping
                    if target_name == 'precipitation':
                        pred_val = max(0.0, round(pred_val, 2))
                    elif target_name == 'relative_humidity':
                        pred_val = min(100.0, max(0.0, round(pred_val, 1)))
                    elif target_name == 'wind_speed':
                        pred_val = max(0.0, round(pred_val, 1))
                    elif target_name == 'temperature':
                        pred_val = round(pred_val, 1)

                    step_preds[target_name] = pred_val
                else:
                    step_preds[target_name] = None

            # Map predicted values back to candidate_df to roll forward
            for t_col, t_val in step_preds.items():
                if t_val is not None:
                    candidate_df.at[len(candidate_df) - 1, t_col] = t_val

            sim_df = candidate_df

            record_dict = {
                'timestamp': next_timestamp.isoformat(),
                'temperature': step_preds.get('temperature'),
                'rainfall': step_preds.get('precipitation'),
                'humidity': step_preds.get('relative_humidity'),
                'wind_speed': step_preds.get('wind_speed'),
            }
            predictions_output.append(record_dict)

            # Persist to database if enabled
            if persist:
                WeatherPrediction.objects.update_or_create(
                    farm=self.farm,
                    model_version=model_version_used,
                    target_timestamp=next_timestamp,
                    defaults={
                        'prediction_timestamp': current_time,
                        'temperature_prediction': step_preds.get('temperature'),
                        'rainfall_prediction': step_preds.get('precipitation'),
                        'humidity_prediction': step_preds.get('relative_humidity'),
                        'wind_speed_prediction': step_preds.get('wind_speed'),
                    }
                )

        return {
            'farm_id': self.farm.id,
            'farm_name': self.farm.farm_name,
            'prediction_type': 'ML_WEATHER',
            'model_version': model_version_used,
            'generated_at': current_time.isoformat(),
            'forecast_horizon': '24h',
            'predictions': predictions_output,
        }
