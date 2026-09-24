from django.urls import path

from .views import (
    CurrentWeatherView,
    HourlyForecastView,
    DailyForecastView,
    RefreshWeatherView,
    HistoricalWeatherView,
    HistoricalSummaryView,
    CollectHistoricalWeatherView,
    ExportHistoricalWeatherView,
)

urlpatterns = [
    path('api/weather/farms/<int:farm_id>/current/', CurrentWeatherView.as_view(), name='current-weather'),
    path('api/weather/farms/<int:farm_id>/hourly/', HourlyForecastView.as_view(), name='hourly-weather'),
    path('api/weather/farms/<int:farm_id>/daily/', DailyForecastView.as_view(), name='daily-weather'),
    path('api/weather/farms/<int:farm_id>/refresh/', RefreshWeatherView.as_view(), name='refresh-weather'),
    # Stage 3 Historical Endpoints (specific subpaths listed before base path)
    path('api/weather/farms/<int:farm_id>/historical/summary/', HistoricalSummaryView.as_view(), name='historical-weather-summary'),
    path('api/weather/farms/<int:farm_id>/historical/collect/', CollectHistoricalWeatherView.as_view(), name='historical-weather-collect'),
    path('api/weather/farms/<int:farm_id>/historical/export/', ExportHistoricalWeatherView.as_view(), name='historical-weather-export'),
    path('api/weather/farms/<int:farm_id>/historical/', HistoricalWeatherView.as_view(), name='historical-weather'),
]
