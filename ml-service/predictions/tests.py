"""
predictions/tests.py

Comprehensive test suite for Stage 5: AI Weather Prediction Models.

Tests:
  1. Feature Engineering (Temporal, Lag, Rolling, No Leakage)
  2. Baseline Model (Persistence / Last-Value)
  3. Model Evaluator (MAE, RMSE, R², MBE)
  4. Dataset Builder (Chronological Split, Validation, No Shuffle)
  5. Model Training & Serialization (RandomForest, Joblib artifact, ModelMetadata DB record)
  6. Weather Prediction Service (Inference, 24h Horizon, Persistence)
  7. API Endpoints (Auth, Ownership, Prediction & Evaluation endpoints)
"""
import os
import shutil
import tempfile
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from farms.models import Farm
from accounts.models import FarmerProfile
from weather.models import Weather
from soil.models import SoilMoisture
from predictions.models import WeatherPrediction, ModelMetadata
from predictions.services.feature_engineering import WeatherFeatureEngineer
from predictions.services.baseline_model import PersistenceBaselineModel
from predictions.services.model_evaluation import ModelEvaluator
from predictions.services.dataset_builder import PredictionDatasetBuilder
from predictions.services.model_training import WeatherModelTrainer
from predictions.services.weather_predictor import (
    WeatherPredictionService,
    ModelNotTrainedError,
    InsufficientDataError,
)


class WeatherFeatureEngineeringTests(TestCase):
    """Tests feature engineering transformations and data leakage safeguards."""

    def setUp(self):
        self.engineer = WeatherFeatureEngineer(resolution='hourly')
        # Create 50 synthetic hourly rows
        base_time = datetime(2026, 9, 1, 0, 0)
        records = []
        for i in range(50):
            t = base_time + timedelta(hours=i)
            records.append({
                'timestamp': t,
                'temperature': 20.0 + (i % 12) * 1.0,
                'precipitation': 0.5 if i % 6 == 0 else 0.0,
                'relative_humidity': 60.0 + (i % 20),
                'wind_speed': 10.0 + (i % 5),
                'evapotranspiration': 0.02,
                'surface_pressure': 1010.0,
                'latitude': 18.5204,
                'longitude': 73.8567,
            })
        self.df = pd.DataFrame(records)

    def test_temporal_features_created(self):
        res = self.engineer.create_features(self.df, drop_warmup=False)
        self.assertIn('hour', res.columns)
        self.assertIn('day', res.columns)
        self.assertIn('day_of_week', res.columns)
        self.assertIn('sin_hour', res.columns)
        self.assertIn('cos_hour', res.columns)
        self.assertIn('sin_month', res.columns)
        self.assertIn('cos_month', res.columns)

    def test_lag_features_created(self):
        res = self.engineer.create_features(self.df, drop_warmup=False)
        for col in ['temperature', 'precipitation', 'relative_humidity', 'wind_speed']:
            for lag in [1, 2, 3, 24]:
                self.assertIn(f'{col}_lag_{lag}', res.columns)

    def test_rolling_features_prevent_data_leakage(self):
        """
        Verify rolling features use shift(1) so current time's value is NEVER leaked.
        """
        res = self.engineer.create_features(self.df, drop_warmup=False)
        self.assertIn('temperature_rolling_mean_3', res.columns)
        # At index 10, temperature_rolling_mean_3 must be the average of temp at indices 7, 8, 9
        expected_mean = self.df.loc[7:9, 'temperature'].mean()
        actual_mean = res.loc[10, 'temperature_rolling_mean_3']
        self.assertAlmostEqual(expected_mean, actual_mean, places=4)

    def test_warmup_rows_dropped_when_requested(self):
        res = self.engineer.create_features(self.df, drop_warmup=True)
        # 50 total - 24 warmup = 26 remaining
        self.assertEqual(len(res), 26)
        # First row in warm dataset should not have NaN for 24h lag
        self.assertFalse(np.isnan(res['temperature_lag_24'].iloc[0]))


class PersistenceBaselineTests(TestCase):
    """Tests the Persistence / Last-Value baseline model."""

    def test_baseline_predictions(self):
        model = PersistenceBaselineModel(target_variable='temperature')
        df = pd.DataFrame({
            'temperature_lag_1': [22.0, 23.5, 25.0],
            'other_col': [1, 2, 3]
        })
        preds = model.predict(df)
        np.testing.assert_array_equal(preds, np.array([22.0, 23.5, 25.0]))


class ModelEvaluatorTests(TestCase):
    """Tests regression metrics calculation."""

    def test_metrics_calculation(self):
        y_true = np.array([20.0, 22.0, 24.0, 26.0])
        y_pred = np.array([21.0, 22.0, 23.0, 27.0])
        # Errors: +1, 0, -1, +1 -> MAE = 3/4 = 0.75
        # Squared errors: 1, 0, 1, 1 -> MSE = 3/4 = 0.75 -> RMSE = sqrt(0.75) ~ 0.866
        # MBE: (1 + 0 - 1 + 1)/4 = 0.25
        metrics = ModelEvaluator.calculate_metrics(y_true, y_pred)
        self.assertEqual(metrics['mae'], 0.75)
        self.assertAlmostEqual(metrics['rmse'], 0.866, places=2)
        self.assertEqual(metrics['mbe'], 0.25)
        self.assertGreater(metrics['r2'], 0.8)

    def test_compare_models(self):
        y_true = np.array([20.0, 22.0, 24.0, 26.0])
        b_pred = np.array([18.0, 20.0, 22.0, 24.0])  # MAE = 2.0
        m_pred = np.array([20.5, 22.0, 23.5, 26.0])  # MAE = 0.25
        report = ModelEvaluator.compare_models(y_true, b_pred, m_pred, target_name='temperature')
        self.assertEqual(report['target'], 'temperature')
        self.assertEqual(report['baseline']['mae'], 2.0)
        self.assertEqual(report['ml_model']['mae'], 0.25)
        self.assertGreater(report['mae_improvement_pct'], 80.0)


class PredictionPipelineIntegrationTests(TestCase):
    """Integration test suite covering DatasetBuilder, ModelTrainer, WeatherPredictionService and APIs."""

    def setUp(self):
        self.client = APIClient()
        self.temp_dir = tempfile.mkdtemp()

        # Farmer 1 & Farm 1
        self.user1 = User.objects.create_user(username='farmer1', password='password123')
        self.profile1 = FarmerProfile.objects.create(
            user=self.user1,
            full_name='Farmer One',
            phone_number='+919876543210'
        )
        self.farm1 = Farm.objects.create(
            farmer=self.profile1,
            farm_name='Test Plot Alpha',
            farm_area=2.5,
            farm_area_unit='acre',
            latitude='18.5204',
            longitude='73.8567',
            village='Haveli',
            district='Pune',
            state='Maharashtra'
        )

        # Farmer 2 & Farm 2 (For ownership tests)
        self.user2 = User.objects.create_user(username='farmer2', password='password123')
        self.profile2 = FarmerProfile.objects.create(
            user=self.user2,
            full_name='Farmer Two',
            phone_number='+919876543211'
        )
        self.farm2 = Farm.objects.create(
            farmer=self.profile2,
            farm_name='Test Plot Beta',
            farm_area=3.0,
            farm_area_unit='acre',
            latitude='19.0000',
            longitude='74.0000',
            village='Baramati',
            district='Pune',
            state='Maharashtra'
        )

        # Create 100 consecutive hourly historical weather records for Farm 1
        start_time = timezone.now() - timedelta(days=5)
        weather_records = []
        for i in range(100):
            t = start_time + timedelta(hours=i)
            weather_records.append(Weather(
                farm=self.farm1,
                timestamp=t,
                forecast_type='HISTORICAL',
                source='OPEN_METEO',
                temperature=22.0 + (i % 8) * 1.5,
                precipitation=1.0 if i % 12 == 0 else 0.0,
                relative_humidity=65.0 + (i % 15),
                wind_speed=12.0 + (i % 6),
                evapotranspiration=0.03,
                surface_pressure=1012.0
            ))
        Weather.objects.bulk_create(weather_records)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_dataset_builder_chronological_split(self):
        builder = PredictionDatasetBuilder(farm_id=self.farm1.id)
        dataset = builder.build_dataset()
        self.assertIn('train', dataset)
        self.assertIn('val', dataset)
        self.assertIn('test', dataset)
        self.assertIn('metadata', dataset)

        # Ensure chronological ordering: train max time < test min time
        train_max = dataset['train']['timestamp'].max()
        test_min = dataset['test']['timestamp'].min()
        self.assertLess(train_max, test_min)

    def test_model_training_and_serialization(self):
        trainer = WeatherModelTrainer(
            farm_id=self.farm1.id,
            artifacts_dir=self.temp_dir,
            version_prefix='test_v1'
        )
        report = trainer.train_all_targets(
            targets=['temperature'],
            n_estimators=10,
            max_depth=5,
        )
        self.assertIn('temperature', report['targets'])
        t_res = report['targets']['temperature']
        self.assertTrue(os.path.exists(t_res['artifact_path']))

        # Verify DB ModelMetadata
        meta = ModelMetadata.objects.get(id=t_res['metadata_id'])
        self.assertTrue(meta.is_active)
        self.assertEqual(meta.target, 'temperature')
        self.assertIsNotNone(meta.model_mae)
        self.assertIsNotNone(meta.baseline_mae)

    def test_weather_prediction_service_generates_24h(self):
        # Train model first
        trainer = WeatherModelTrainer(
            farm_id=self.farm1.id,
            artifacts_dir=self.temp_dir,
            version_prefix='test_v1'
        )
        trainer.train_all_targets(
            targets=['temperature', 'precipitation', 'relative_humidity', 'wind_speed'],
            n_estimators=10,
            max_depth=5
        )

        service = WeatherPredictionService(farm=self.farm1)
        res = service.predict_24h(persist=True)
        self.assertEqual(res['farm_id'], self.farm1.id)
        self.assertEqual(res['prediction_type'], 'ML_WEATHER')
        self.assertEqual(len(res['predictions']), 24)

        # Verify records persisted in DB
        db_preds = WeatherPrediction.objects.filter(farm=self.farm1)
        self.assertEqual(db_preds.count(), 24)
        first_p = db_preds.first()
        self.assertIsNotNone(first_p.temperature_prediction)

    def test_weather_prediction_api_unauthenticated(self):
        url = f'/api/predictions/farms/{self.farm1.id}/weather/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_weather_prediction_api_farm_ownership(self):
        # Authenticate as Farmer 2, attempt to access Farm 1
        self.client.force_authenticate(user=self.user2)
        url = f'/api/predictions/farms/{self.farm1.id}/weather/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_weather_prediction_api_success(self):
        # Train models for Farm 1
        trainer = WeatherModelTrainer(
            farm_id=self.farm1.id,
            artifacts_dir=self.temp_dir,
            version_prefix='test_v1'
        )
        trainer.train_all_targets(
            targets=['temperature', 'precipitation', 'relative_humidity', 'wind_speed'],
            n_estimators=10,
            max_depth=5
        )

        self.client.force_authenticate(user=self.user1)
        url = f'/api/predictions/farms/{self.farm1.id}/weather/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['farm_id'], self.farm1.id)
        self.assertEqual(data['prediction_type'], 'ML_WEATHER')
        self.assertIn('predictions', data)
        self.assertEqual(len(data['predictions']), 24)
        self.assertIn('model_info', data)

    def test_evaluation_api_success(self):
        # Train models for Farm 1
        trainer = WeatherModelTrainer(
            farm_id=self.farm1.id,
            artifacts_dir=self.temp_dir,
            version_prefix='test_v1'
        )
        trainer.train_all_targets(
            targets=['temperature'],
            n_estimators=10,
            max_depth=5
        )

        self.client.force_authenticate(user=self.user1)
        url = f'/api/predictions/farms/{self.farm1.id}/weather/evaluation/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('targets', data)
        self.assertIn('temperature', data['targets'])
        temp_data = data['targets']['temperature']
        self.assertIn('baseline', temp_data)
        self.assertIn('ml_model', temp_data)
        self.assertIn('mae', temp_data['ml_model'])
