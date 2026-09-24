"""
Weather API Views — Stage 2 & Stage 3.

Endpoints:
  GET  /api/weather/farms/{farm_id}/current/             — Most recent current weather
  GET  /api/weather/farms/{farm_id}/hourly/              — Hourly forecast (next 24 h)
  GET  /api/weather/farms/{farm_id}/daily/               — Daily forecast (next 7 days)
  POST /api/weather/farms/{farm_id}/refresh/             — Force-refresh forecast weather data

Stage 3 Historical Endpoints:
  GET  /api/weather/farms/{farm_id}/historical/         — Query historical weather records (start_date, end_date)
  GET  /api/weather/farms/{farm_id}/historical/summary/ — Calculate historical summary & quality indicators
  POST /api/weather/farms/{farm_id}/historical/collect/ — Collect & process historical data for date range
  GET  /api/weather/farms/{farm_id}/historical/export/  — Export clean historical dataset (format=csv|parquet)

Authorization:
  - All endpoints require authentication (Token header).
  - A farmer can only access weather for their own farms.
"""
import logging
from datetime import datetime, timedelta, date

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from farms.models import Farm
from .models import ForecastTypeChoices
from .serializers import WeatherSerializer
from .services.weather_service import WeatherService
from .services.historical_weather_service import HistoricalWeatherService

logger = logging.getLogger(__name__)


def parse_date_params(request):
    """Parse and validate start_date and end_date query/body parameters."""
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')

    if not start_date_str and request.method == 'POST' and hasattr(request, 'data'):
        start_date_str = request.data.get('start_date')
    if not end_date_str and request.method == 'POST' and hasattr(request, 'data'):
        end_date_str = request.data.get('end_date')

    today = date.today()
    if not end_date_str:
        end_d = today
        end_date_str = end_d.strftime('%Y-%m-%d')
    else:
        try:
            end_d = datetime.strptime(str(end_date_str), '%Y-%m-%d').date()
        except ValueError:
            return None, None, "Invalid end_date format. Use YYYY-MM-DD."

    if not start_date_str:
        start_d = end_d - timedelta(days=30)
        start_date_str = start_d.strftime('%Y-%m-%d')
    else:
        try:
            start_d = datetime.strptime(str(start_date_str), '%Y-%m-%d').date()
        except ValueError:
            return None, None, "Invalid start_date format. Use YYYY-MM-DD."

    if start_d > end_d:
        return None, None, "'start_date' cannot be after 'end_date'."

    max_days = getattr(settings, 'HISTORICAL_MAX_RANGE_DAYS', 365)
    if (end_d - start_d).days > max_days:
        return None, None, f"Requested date range exceeds maximum allowed limit of {max_days} days."

    return start_date_str, end_date_str, None


class FarmOwnershipMixin:
    """Mixin to ensure the requested farm belongs to the requesting farmer."""
    permission_classes = [IsAuthenticated]

    def get_farm(self, farm_id):
        farmer_profile = self.request.user.farmer_profile
        return get_object_or_404(Farm, pk=farm_id, farmer=farmer_profile)

    def _farm_location(self, farm):
        return {
            "latitude": float(farm.latitude),
            "longitude": float(farm.longitude),
            "name": farm.farm_name,
            "village": farm.village or "",
            "city": farm.city or "",
            "district": farm.district or "",
            "state": farm.state or "",
            "country": farm.country or "",
        }

    def _build_response(self, farm, forecast_type, weather_objects):
        serializer = WeatherSerializer(weather_objects, many=True)
        return Response({
            "farm_id": farm.id,
            "location": self._farm_location(farm),
            "source": "OPEN_METEO",
            "forecast_type": forecast_type,
            "count": len(weather_objects),
            "results": serializer.data,
        })


class CurrentWeatherView(FarmOwnershipMixin, APIView):
    """Return the current weather for a farm (cached or freshly fetched)."""

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        try:
            data = WeatherService.get_weather(farm, ForecastTypeChoices.CURRENT)
        except Exception as exc:
            logger.error(f"CurrentWeatherView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": "Weather data is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not data:
            return Response(
                {"detail": "No current weather data available. Try refreshing."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return self._build_response(farm, ForecastTypeChoices.CURRENT, data)


class HourlyForecastView(FarmOwnershipMixin, APIView):
    """Return hourly forecast (next ~24 h) for a farm."""

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        try:
            data = WeatherService.get_weather(farm, ForecastTypeChoices.HOURLY)
        except Exception as exc:
            logger.error(f"HourlyForecastView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": "Hourly forecast data is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._build_response(farm, ForecastTypeChoices.HOURLY, data)


class DailyForecastView(FarmOwnershipMixin, APIView):
    """Return daily forecast (next ~7 days) for a farm."""

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        try:
            data = WeatherService.get_weather(farm, ForecastTypeChoices.DAILY)
        except Exception as exc:
            logger.error(f"DailyForecastView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": "Daily forecast data is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._build_response(farm, ForecastTypeChoices.DAILY, data)


class RefreshWeatherView(FarmOwnershipMixin, APIView):
    """Force-refresh forecast weather data for a farm."""

    def post(self, request, farm_id):
        farm = self.get_farm(farm_id)
        try:
            WeatherService.refresh_all(farm)
        except Exception as exc:
            logger.error(f"RefreshWeatherView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": "Failed to refresh weather data. The weather service may be temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        current_data = WeatherService.get_weather(farm, ForecastTypeChoices.CURRENT)
        serializer = WeatherSerializer(current_data, many=True)
        return Response({
            "detail": "Weather data refreshed successfully.",
            "farm_id": farm.id,
            "location": self._farm_location(farm),
            "current_count": len(current_data),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


# ── Stage 3 Historical Views ─────────────────────────────────────────────────

class HistoricalWeatherView(FarmOwnershipMixin, APIView):
    """
    GET /api/weather/farms/{farm_id}/historical/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

    Return historical weather records for a farm location and date range.
    """

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        start_date, end_date, error_msg = parse_date_params(request)
        if error_msg:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            records = HistoricalWeatherService.get_historical_weather(farm, start_date, end_date)
        except Exception as exc:
            logger.error(f"HistoricalWeatherView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": f"Failed to retrieve historical weather: {str(exc)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = WeatherSerializer(records, many=True)
        return Response({
            "farm_id": farm.id,
            "location": self._farm_location(farm),
            "source": "OPEN_METEO",
            "forecast_type": "HISTORICAL",
            "start_date": start_date,
            "end_date": end_date,
            "count": len(records),
            "results": serializer.data,
        })


class HistoricalSummaryView(FarmOwnershipMixin, APIView):
    """
    GET /api/weather/farms/{farm_id}/historical/summary/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

    Return historical summary statistics and data quality report for a farm.
    """

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        start_date, end_date, error_msg = parse_date_params(request)
        if error_msg:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            summary = HistoricalWeatherService.get_historical_summary(farm, start_date, end_date)
            summary["location"] = self._farm_location(farm)
            return Response(summary, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.error(f"HistoricalSummaryView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": f"Failed to calculate historical summary: {str(exc)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class CollectHistoricalWeatherView(FarmOwnershipMixin, APIView):
    """
    POST /api/weather/farms/{farm_id}/historical/collect/

    Body: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    Triggers historical collection and data processing pipeline for the farm.
    """

    def post(self, request, farm_id):
        farm = self.get_farm(farm_id)
        start_date, end_date, error_msg = parse_date_params(request)
        if error_msg:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            records, quality_report = HistoricalWeatherService.collect_and_process(farm, start_date, end_date)
            return Response({
                "detail": "Historical weather collected and processed successfully.",
                "farm_id": farm.id,
                "location": self._farm_location(farm),
                "start_date": start_date,
                "end_date": end_date,
                "count": len(records),
                "quality_report": quality_report,
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.error(f"CollectHistoricalWeatherView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": f"Historical data collection failed: {str(exc)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class ExportHistoricalWeatherView(FarmOwnershipMixin, APIView):
    """
    GET /api/weather/farms/{farm_id}/historical/export/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&format=csv|parquet

    Export cleaned historical weather dataset as CSV or Parquet download.
    """

    def get(self, request, farm_id):
        print(f"DEBUG: ExportHistoricalWeatherView called for farm_id={farm_id}, user={request.user}")
        try:
            farm = self.get_farm(farm_id)
        except Exception as e:
            print(f"DEBUG: get_farm failed: {e}")
            raise
        start_date, end_date, error_msg = parse_date_params(request)
        if error_msg:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        format_type = request.query_params.get('format', 'csv').lower()

        try:
            if format_type == 'parquet':
                dataset_bytes = HistoricalWeatherService.export_dataset(farm, start_date, end_date, format_type='parquet')
                response = HttpResponse(dataset_bytes, content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="historical_weather_farm_{farm.id}_{start_date}_{end_date}.parquet"'
                return response
            else:
                dataset_csv = HistoricalWeatherService.export_dataset(farm, start_date, end_date, format_type='csv')
                response = HttpResponse(dataset_csv, content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="historical_weather_farm_{farm.id}_{start_date}_{end_date}.csv"'
                return response
        except NotImplementedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error(f"ExportHistoricalWeatherView error for farm {farm_id}: {exc}")
            return Response(
                {"detail": f"Failed to export historical dataset: {str(exc)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
