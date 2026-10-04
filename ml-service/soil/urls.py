"""
soil/urls.py

URL patterns for Stage 4: Soil Moisture & Farm Environmental State.
"""
from django.urls import path
from .views import (
    SensorIngestionView,
    CurrentSoilMoistureView,
    SoilMoistureHistoryView,
    EnvironmentalStateView,
)

urlpatterns = [
    # ── Sensor Ingestion API ──────────────────────────────────────────
    path('api/soil-moisture/sensor/', SensorIngestionView.as_view(), name='soil-moisture-sensor-ingest'),

    # ── Soil Moisture Queries ─────────────────────────────────────────
    path('api/soil-moisture/farms/<int:farm_id>/current/', CurrentSoilMoistureView.as_view(), name='soil-moisture-current'),
    path('api/soil-moisture/farms/<int:farm_id>/history/', SoilMoistureHistoryView.as_view(), name='soil-moisture-history'),

    # ── Farm Environmental State API ──────────────────────────────────
    path('api/environment/farms/<int:farm_id>/state/', EnvironmentalStateView.as_view(), name='environmental-state'),
]
