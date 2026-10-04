"""
predictions/urls.py

URL patterns for Stage 5: AI Weather Prediction Models.
"""
from django.urls import path
from .views import (
    FarmWeatherPredictionView,
    FarmPredictionEvaluationView,
)

urlpatterns = [
    path('api/predictions/farms/<int:farm_id>/weather/evaluation/', FarmPredictionEvaluationView.as_view(), name='farm-prediction-evaluation'),
    path('api/predictions/farms/<int:farm_id>/weather/', FarmWeatherPredictionView.as_view(), name='farm-weather-prediction'),
]
