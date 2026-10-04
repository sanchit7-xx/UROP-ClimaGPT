"""
predictions/services/model_training.py

Model training pipeline for Stage 5: AI Weather Prediction Models.

Orchestrates:
  1. Loading historical data via PredictionDatasetBuilder
  2. Training naive PersistenceBaselineModel
  3. Training scikit-learn RandomForestRegressor for each weather target
  4. Evaluating both models on the chronological test split
  5. Serializing trained models to disk via joblib
  6. Storing ModelMetadata in database for research traceability
"""
import os
import logging
from typing import Dict, Any, List, Optional
import joblib
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor

from predictions.models import ModelMetadata
from farms.models import Farm
from .dataset_builder import PredictionDatasetBuilder
from .baseline_model import PersistenceBaselineModel
from .model_evaluation import ModelEvaluator

logger = logging.getLogger(__name__)


class WeatherModelTrainer:
    """Trains, evaluates, and persists machine learning weather prediction models."""

    TARGET_MAP = {
        'temperature': 'temperature',
        'precipitation': 'precipitation',
        'rainfall': 'precipitation',  # alias
        'relative_humidity': 'relative_humidity',
        'humidity': 'relative_humidity',  # alias
        'wind_speed': 'wind_speed',
    }

    def __init__(
        self,
        farm_id: Optional[int] = None,
        artifacts_dir: Optional[str] = None,
        version_prefix: str = 'weather_v1',
    ):
        self.farm_id = farm_id
        self.artifacts_dir = artifacts_dir or getattr(
            settings, 'MODEL_ARTIFACTS_DIR',
            os.path.join(settings.BASE_DIR, 'predictions', 'ml', 'artifacts')
        )
        self.version_prefix = version_prefix
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def train_all_targets(
        self,
        targets: Optional[List[str]] = None,
        n_estimators: int = 100,
        max_depth: Optional[int] = 12,
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Trains separate Random Forest regressors for each weather target variable.
        """
        if targets is None:
            targets = ['temperature', 'precipitation', 'relative_humidity', 'wind_speed']

        dataset_builder = PredictionDatasetBuilder(farm_id=self.farm_id)
        dataset = dataset_builder.build_dataset()

        results = {}
        for target in targets:
            norm_target = self.TARGET_MAP.get(target.lower(), target.lower())
            logger.info(f"Starting training for target: {norm_target} (farm_id={self.farm_id})")
            target_result = self.train_single_target(
                dataset_builder=dataset_builder,
                dataset=dataset,
                target_name=norm_target,
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=random_state,
            )
            results[norm_target] = target_result

        return {
            'farm_id': self.farm_id,
            'dataset_metadata': dataset['metadata'],
            'targets': results,
        }

    def train_single_target(
        self,
        dataset_builder: PredictionDatasetBuilder,
        dataset: Dict[str, Any],
        target_name: str,
        n_estimators: int = 100,
        max_depth: Optional[int] = 12,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """
        Trains and persists ML model and baseline for a single target variable.
        """
        X_train, y_train, X_val, y_val, X_test, y_test, feature_cols = dataset_builder.prepare_target_data(
            dataset, target_name=target_name
        )

        # 1. Baseline Model (Persistence / Last-Value)
        baseline = PersistenceBaselineModel(target_variable=target_name)
        baseline.fit(X_train, y_train)
        baseline_test_pred = baseline.predict(dataset['test'])

        # 2. Machine Learning Model (Random Forest Regressor)
        rf = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        ml_test_pred = rf.predict(X_test)

        # Ensure precipitation predictions are never negative
        if target_name in ('precipitation', 'rainfall'):
            ml_test_pred = np_clip_zero(ml_test_pred)
            baseline_test_pred = np_clip_zero(baseline_test_pred)
        elif target_name in ('relative_humidity', 'humidity'):
            ml_test_pred = np_clip_bounds(ml_test_pred, 0.0, 100.0)
            baseline_test_pred = np_clip_bounds(baseline_test_pred, 0.0, 100.0)
        elif target_name in ('wind_speed',):
            ml_test_pred = np_clip_zero(ml_test_pred)
            baseline_test_pred = np_clip_zero(baseline_test_pred)

        # 3. Model Evaluation Comparison
        eval_report = ModelEvaluator.compare_models(
            y_true=y_test.to_numpy(),
            baseline_pred=baseline_test_pred,
            ml_pred=ml_test_pred,
            target_name=target_name,
        )

        # Feature importances
        importances = {}
        if hasattr(rf, 'feature_importances_'):
            for feat, imp in zip(feature_cols, rf.feature_importances_):
                importances[feat] = round(float(imp), 4)
            # Sort descending
            importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True)[:15])

        # 4. Serialize Model Artifact
        farm_suffix = f"_farm_{self.farm_id}" if self.farm_id else "_global"
        version_tag = f"{self.version_prefix}_{target_name}{farm_suffix}"
        artifact_filename = f"{version_tag}.joblib"
        artifact_filepath = os.path.join(self.artifacts_dir, artifact_filename)

        model_payload = {
            'model': rf,
            'target': target_name,
            'features': feature_cols,
            'version': version_tag,
            'hyperparameters': {
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'random_state': random_state,
            },
            'metrics': eval_report,
        }
        joblib.dump(model_payload, artifact_filepath)
        logger.info(f"Model artifact saved to: {artifact_filepath}")

        # 5. Persist ModelMetadata in Database
        farm_instance = None
        if self.farm_id:
            try:
                farm_instance = Farm.objects.get(id=self.farm_id)
            except Farm.DoesNotExist:
                pass

        # Deactivate previous active models for same target and farm
        ModelMetadata.objects.filter(
            farm=farm_instance,
            target=target_name,
            is_active=True
        ).update(is_active=False)

        metadata_obj = ModelMetadata.objects.create(
            farm=farm_instance,
            target=target_name,
            model_name='RandomForestRegressor',
            version=version_tag,
            training_start=dataset['metadata']['train_start'],
            training_end=dataset['metadata']['train_end'],
            test_start=dataset['metadata']['test_start'],
            test_end=dataset['metadata']['test_end'],
            sample_count=dataset['metadata']['total_samples'],
            train_samples=dataset['metadata']['train_samples'],
            val_samples=dataset['metadata']['val_samples'],
            test_samples=dataset['metadata']['test_samples'],
            baseline_mae=eval_report['baseline']['mae'],
            baseline_rmse=eval_report['baseline']['rmse'],
            baseline_r2=eval_report['baseline']['r2'],
            baseline_mbe=eval_report['baseline']['mbe'],
            model_mae=eval_report['ml_model']['mae'],
            model_rmse=eval_report['ml_model']['rmse'],
            model_r2=eval_report['ml_model']['r2'],
            model_mbe=eval_report['ml_model']['mbe'],
            features=feature_cols,
            feature_importances=importances,
            hyperparameters={
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'random_state': random_state,
            },
            artifact_path=artifact_filepath,
            is_active=True,
            notes=f"Chronological split 70/15/15. MAE Improvement: {eval_report['mae_improvement_pct']}%"
        )

        return {
            'target': target_name,
            'version': version_tag,
            'artifact_path': artifact_filepath,
            'evaluation': eval_report,
            'metadata_id': metadata_obj.id,
            'top_features': list(importances.items())[:5],
        }


def np_clip_zero(arr):
    import numpy as np
    return np.clip(arr, 0.0, None)


def np_clip_bounds(arr, low, high):
    import numpy as np
    return np.clip(arr, low, high)
