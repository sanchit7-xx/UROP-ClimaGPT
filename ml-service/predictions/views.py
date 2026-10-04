"""
predictions/views.py

API Views for Stage 5: AI Weather Prediction Models.

Endpoints:
  - GET /api/predictions/farms/<farm_id>/weather/
      Returns latest 24h ML weather predictions (Temperature, Rainfall, Humidity, Wind).
  - GET /api/predictions/farms/<farm_id>/weather/evaluation/
      Returns research evaluation metrics comparing Baseline vs ML Model.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from weather.views import FarmOwnershipMixin
from predictions.models import WeatherPrediction, ModelMetadata
from predictions.services.weather_predictor import (
    WeatherPredictionService,
    ModelNotTrainedError,
    InsufficientDataError,
)

logger = logging.getLogger(__name__)


class FarmWeatherPredictionView(FarmOwnershipMixin, APIView):
    """
    Returns the latest ML-generated short-term weather prediction for a farmer's farm.
    
    Response format conforms to Stage 5 specification:
      - farm_id
      - prediction_type: 'ML_WEATHER'
      - model_version
      - generated_at
      - forecast_horizon: '24h'
      - predictions: list of hourly predictions
      - model_info: transparency details (model name, training period, sample count)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, farm_id: int):
        farm = self.get_farm(farm_id)
        force_refresh = request.query_params.get('refresh', '').lower() in ('true', '1')

        # Check if active model exists
        active_models_qs = ModelMetadata.objects.filter(
            farm=farm, is_active=True
        )
        if not active_models_qs.exists():
            active_models_qs = ModelMetadata.objects.filter(
                farm__isnull=True, is_active=True
            )

        if not active_models_qs.exists():
            return Response(
                {
                    "status": "unavailable",
                    "error": "MODEL_NOT_TRAINED",
                    "message": "AI weather prediction is not available yet because the model has not been trained for this farm.",
                    "farm_id": farm.id,
                },
                status=status.HTTP_404_NOT_FOUND
            )

        primary_meta = active_models_qs.first()
        now = timezone.now()

        # Check for cached recent predictions (within 1 hour)
        if not force_refresh:
            cached_qs = WeatherPrediction.objects.filter(
                farm=farm,
                target_timestamp__gte=now - timedelta(hours=1),
                prediction_timestamp__gte=now - timedelta(hours=2)
            ).order_by('target_timestamp')[:24]

            if cached_qs.count() >= 12:
                predictions_list = []
                for p in cached_qs:
                    predictions_list.append({
                        'timestamp': p.target_timestamp.isoformat(),
                        'temperature': p.temperature_prediction,
                        'rainfall': p.rainfall_prediction,
                        'humidity': p.humidity_prediction,
                        'wind_speed': p.wind_speed_prediction,
                    })

                return Response({
                    "farm_id": farm.id,
                    "farm_name": farm.farm_name,
                    "prediction_type": "ML_WEATHER",
                    "model_version": primary_meta.version,
                    "generated_at": cached_qs[0].prediction_timestamp.isoformat(),
                    "forecast_horizon": "24h",
                    "predictions": predictions_list,
                    "model_info": {
                        "model_name": primary_meta.model_name,
                        "version": primary_meta.version,
                        "sample_count": primary_meta.sample_count,
                        "training_period": f"{primary_meta.training_start.strftime('%Y-%m-%d') if primary_meta.training_start else 'N/A'} to {primary_meta.training_end.strftime('%Y-%m-%d') if primary_meta.training_end else 'N/A'}",
                        "last_trained": primary_meta.trained_at.isoformat(),
                    }
                })

        # Generate fresh inference
        predictor = WeatherPredictionService(farm=farm)
        try:
            result = predictor.predict_24h(persist=True)
            result["model_info"] = {
                "model_name": primary_meta.model_name,
                "version": primary_meta.version,
                "sample_count": primary_meta.sample_count,
                "training_period": f"{primary_meta.training_start.strftime('%Y-%m-%d') if primary_meta.training_start else 'N/A'} to {primary_meta.training_end.strftime('%Y-%m-%d') if primary_meta.training_end else 'N/A'}",
                "last_trained": primary_meta.trained_at.isoformat(),
            }
            return Response(result, status=status.HTTP_200_OK)
        except InsufficientDataError as e:
            return Response(
                {
                    "status": "insufficient_data",
                    "error": "INSUFFICIENT_DATA",
                    "message": "AI weather prediction is not available yet because sufficient historical data has not been collected.",
                    "detail": str(e),
                    "farm_id": farm.id,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ModelNotTrainedError as e:
            return Response(
                {
                    "status": "unavailable",
                    "error": "MODEL_NOT_TRAINED",
                    "message": "AI weather prediction is not available yet because the model has not been trained.",
                    "detail": str(e),
                    "farm_id": farm.id,
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Prediction inference error for farm {farm.id}: {e}")
            return Response(
                {
                    "status": "error",
                    "error": "PREDICTION_FAILED",
                    "message": "An error occurred while generating AI weather predictions.",
                    "detail": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FarmPredictionEvaluationView(FarmOwnershipMixin, APIView):
    """
    Returns research performance metrics comparing naive baseline against ML models.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, farm_id: int):
        farm = self.get_farm(farm_id)

        metas = ModelMetadata.objects.filter(farm=farm, is_active=True)
        if not metas.exists():
            metas = ModelMetadata.objects.filter(farm__isnull=True, is_active=True)

        if not metas.exists():
            return Response(
                {
                    "status": "unavailable",
                    "error": "NO_EVALUATION_DATA",
                    "message": "Evaluation metrics are not available because no trained models were found.",
                    "farm_id": farm.id,
                },
                status=status.HTTP_404_NOT_FOUND
            )

        targets_dict = {}
        first_meta = metas.first()

        for m in metas:
            target_key = m.target
            # Compute improvement percentage
            b_mae = m.baseline_mae or 0.0
            m_mae = m.model_mae or 0.0
            improvement_pct = round(((b_mae - m_mae) / b_mae) * 100.0, 2) if b_mae > 1e-6 else 0.0

            targets_dict[target_key] = {
                "target": m.target,
                "model_name": m.model_name,
                "version": m.version,
                "baseline": {
                    "mae": m.baseline_mae,
                    "rmse": m.baseline_rmse,
                    "r2": m.baseline_r2,
                    "mbe": m.baseline_mbe,
                },
                "ml_model": {
                    "mae": m.model_mae,
                    "rmse": m.model_rmse,
                    "r2": m.model_r2,
                    "mbe": m.model_mbe,
                },
                "improvement_pct": improvement_pct,
                "top_features": m.feature_importances,
            }

        return Response({
            "farm_id": farm.id,
            "farm_name": farm.farm_name,
            "model_version": first_meta.version,
            "sample_count": first_meta.sample_count,
            "train_samples": first_meta.train_samples,
            "val_samples": first_meta.val_samples,
            "test_samples": first_meta.test_samples,
            "training_period": f"{first_meta.training_start.strftime('%Y-%m-%d') if first_meta.training_start else 'N/A'} to {first_meta.training_end.strftime('%Y-%m-%d') if first_meta.training_end else 'N/A'}",
            "test_period": f"{first_meta.test_start.strftime('%Y-%m-%d') if first_meta.test_start else 'N/A'} to {first_meta.test_end.strftime('%Y-%m-%d') if first_meta.test_end else 'N/A'}",
            "last_trained": first_meta.trained_at.isoformat(),
            "targets": targets_dict,
        })
