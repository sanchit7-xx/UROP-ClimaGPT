"""
WeatherService — Stage 2 Implementation.

Responsibilities:
1. Receive farm coordinates.
2. Call the selected weather provider (via WeatherProviderFactory).
3. Validate provider response.
4. Normalize and save weather data.
5. Return cached or freshly fetched data.

Caching policy:
  - WEATHER_CACHE_MINUTES env var controls how long in-memory cache is valid.
  - Database is used for persistence; in-memory cache reduces DB hits.
  - Cache is invalidated on refresh.
  - No Redis/Celery required for Stage 2.

Architecture notes:
  - Provider-specific parsing stays inside OpenMeteoProvider.
  - This service is provider-agnostic; it works with any WeatherProvider subclass.
  - Future providers (IMD, ECMWF, GFS, NASA) can be added to the factory
    without modifying this service.
"""
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache

from farms.models import Farm
from . import WeatherProviderFactory
from ..models import Weather, ForecastTypeChoices, WeatherSourceChoices

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Service layer handling weather data retrieval, caching, and persistence.

    All methods are static — no instance state is needed.
    """

    @staticmethod
    def _cache_key(farm_id: int, forecast_type: str) -> str:
        return f"weather:{farm_id}:{forecast_type}"

    @staticmethod
    def _parse_timestamp(ts):
        """Parse a timestamp string or datetime to a timezone-aware datetime."""
        if ts is None:
            return datetime.now(timezone.utc)
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        try:
            # ISO format strings from Open-Meteo: '2026-09-22T10:00' or '2026-09-22T12:00:00'
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp '{ts}', using current UTC time.")
            return datetime.now(timezone.utc)

    @staticmethod
    def _fetch_and_store(farm: Farm, forecast_type: str) -> list:
        """
        Fetch fresh weather data from the provider, store in DB, and cache.

        Returns a list of Weather model instances.
        """
        provider = WeatherProviderFactory.get_provider()
        lat = float(farm.latitude)
        lon = float(farm.longitude)

        try:
            if forecast_type == ForecastTypeChoices.CURRENT:
                raw_data = provider.fetch_current(lat, lon)
            elif forecast_type == ForecastTypeChoices.HOURLY:
                raw_data = provider.fetch_hourly(lat, lon)
            elif forecast_type == ForecastTypeChoices.DAILY:
                raw_data = provider.fetch_daily(lat, lon)
            else:
                raw_data = []
        except Exception as exc:
            logger.error(f"Weather provider error for farm {farm.id}: {exc}")
            raise

        objs = []
        for entry in raw_data:
            ts = WeatherService._parse_timestamp(entry.get('timestamp'))

            obj, _ = Weather.objects.update_or_create(
                farm=farm,
                timestamp=ts,
                forecast_type=forecast_type,
                source=WeatherSourceChoices.OPEN_METEO,
                defaults={
                    'temperature': entry.get('temperature'),
                    'apparent_temperature': entry.get('apparent_temperature'),
                    'precipitation': entry.get('precipitation'),
                    'rain': entry.get('rain'),
                    'relative_humidity': entry.get('relative_humidity'),
                    'wind_speed': entry.get('wind_speed'),
                    'wind_direction': entry.get('wind_direction'),
                    'surface_pressure': entry.get('surface_pressure'),
                    'evapotranspiration': entry.get('evapotranspiration'),
                    'precipitation_probability': entry.get('precipitation_probability'),
                    'weather_code': entry.get('weather_code'),
                },
            )
            objs.append(obj)

        cache_timeout = getattr(settings, 'WEATHER_CACHE_MINUTES', 30) * 60
        cache.set(
            WeatherService._cache_key(farm.id, forecast_type),
            objs,
            timeout=cache_timeout,
        )
        logger.info(
            f"Fetched and stored {len(objs)} {forecast_type} records for farm {farm.id}."
        )
        return objs

    @staticmethod
    def get_weather(farm: Farm, forecast_type: str) -> list:
        """
        Return a list of Weather model instances.

        Uses in-memory cache when available; otherwise fetches from provider
        and persists to database.
        """
        key = WeatherService._cache_key(farm.id, forecast_type)
        cached = cache.get(key)
        if cached is not None:
            logger.debug(f"Cache hit for farm {farm.id} {forecast_type}")
            return cached
        return WeatherService._fetch_and_store(farm, forecast_type)

    @staticmethod
    def refresh_all(farm: Farm) -> None:
        """
        Force-refresh all forecast types for a given farm.

        Clears in-memory cache and re-fetches current, hourly, and daily data
        from the weather provider. Persists fresh data to the database.
        """
        for ft in [ForecastTypeChoices.CURRENT, ForecastTypeChoices.HOURLY, ForecastTypeChoices.DAILY]:
            cache.delete(WeatherService._cache_key(farm.id, ft))
            try:
                WeatherService._fetch_and_store(farm, ft)
            except Exception as exc:
                logger.error(f"Failed to refresh {ft} for farm {farm.id}: {exc}")
                raise
        logger.info(f"All weather data refreshed for farm {farm.id}.")
