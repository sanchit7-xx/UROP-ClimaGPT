"""
Open-Meteo Weather Provider — Stage 2 Complete Implementation.

Uses the Open-Meteo public API (https://api.open-meteo.com/v1/forecast).
No API key required.

Fetches:
  - Current weather:  temperature, apparent_temperature, relative_humidity,
                      precipitation, rain, wind_speed, wind_direction,
                      surface_pressure, weather_code
  - Hourly forecast:  next 24 hours with all above + precipitation_probability,
                      evapotranspiration
  - Daily forecast:   next 7 days with max/min temp, precipitation sum,
                      precipitation_probability_max, wind_speed_max,
                      wind_direction_dominant, sunrise, sunset, et0 ET

All parsing and normalization is contained here.
The WeatherService calls this provider and is unaware of provider-specific fields.
"""
import logging
from datetime import datetime, timezone

import requests

from .provider import WeatherProvider

logger = logging.getLogger(__name__)

# Request timeout in seconds
REQUEST_TIMEOUT = 10


def _safe_get(lst, idx, default=None):
    """Safely retrieve an element from a list by index, returning default on failure."""
    try:
        val = lst[idx]
        return val if val is not None else default
    except (IndexError, TypeError):
        return default


def _validate_humidity(value):
    """Relative humidity must be 0–100. Return None if out of range."""
    if value is None:
        return None
    try:
        v = float(value)
        if 0 <= v <= 100:
            return v
        logger.warning(f"Invalid relative_humidity value: {value}")
        return None
    except (TypeError, ValueError):
        return None


class OpenMeteoProvider(WeatherProvider):
    """
    Concrete weather provider backed by the Open-Meteo public forecast API.

    Provider abstraction allows future providers (IMD, ECMWF, GFS, NASA, etc.)
    to be swapped in without modifying WeatherService or views.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def _make_request(self, latitude: float, longitude: float, params: dict) -> dict:
        """
        Make a GET request to Open-Meteo API.

        Raises:
            requests.HTTPError: on non-2xx status codes
            requests.Timeout:   if the server takes too long
            requests.RequestException: on connection errors
        """
        params.update({
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "UTC",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        })
        response = requests.get(self.BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ── Current Weather ─────────────────────────────────────────────────────

    def fetch_current(self, latitude: float, longitude: float) -> list:
        """
        Fetch current weather conditions for the given coordinates.

        Returns a list with a single dict matching Weather model fields.
        """
        data = self._make_request(
            latitude,
            longitude,
            {
                "current": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "relative_humidity_2m,"
                    "precipitation,"
                    "rain,"
                    "wind_speed_10m,"
                    "wind_direction_10m,"
                    "surface_pressure,"
                    "weather_code,"
                    "et0_fao_evapotranspiration"
                ),
                "hourly": "precipitation_probability",
                "forecast_hours": 1,
            },
        )

        current = data.get("current", {})
        if not current:
            logger.warning("Open-Meteo returned empty 'current' section.")
            return []

        timestamp = current.get("time")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        # Determine precipitation probability for the current timestamp
        hourly_data = data.get("hourly", {})
        hourly_probs = hourly_data.get("precipitation_probability", [])
        times = hourly_data.get("time", [])
        try:
            idx = times.index(timestamp)
        except ValueError:
            idx = 0
        current_prob = _safe_get(hourly_probs, idx)

        return [
            {
                "timestamp": timestamp,
                "temperature": current.get("temperature_2m"),
                "apparent_temperature": current.get("apparent_temperature"),
                "relative_humidity": _validate_humidity(current.get("relative_humidity_2m")),
                "precipitation": current.get("precipitation"),
                "rain": current.get("rain"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_direction": current.get("wind_direction_10m"),
                "surface_pressure": current.get("surface_pressure"),
                "evapotranspiration": current.get("et0_fao_evapotranspiration"),
                "weather_code": current.get("weather_code"),
                "precipitation_probability": current_prob,
            }
        ]

    # ── Hourly Forecast ─────────────────────────────────────────────────────

    def fetch_hourly(self, latitude: float, longitude: float) -> list:
        """
        Fetch hourly forecast for the next 24 hours.

        Returns a list of up to 24 dicts matching Weather model fields.
        """
        data = self._make_request(
            latitude,
            longitude,
            {
                "hourly": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "precipitation_probability,"
                    "relative_humidity_2m,"
                    "wind_speed_10m,"
                    "wind_direction_10m,"
                    "weather_code,"
                    "et0_fao_evapotranspiration"
                ),
                "forecast_days": 2,  # Fetch 2 days so we can slice exactly 24 hours from now
            },
        )

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            logger.warning("Open-Meteo returned empty 'hourly' section.")
            return []

        # Find the index of the current hour to get the next 24 hours
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
        start_idx = 0
        for i, t in enumerate(times):
            if t >= now_str:
                start_idx = i
                break

        result = []
        for idx in range(start_idx, min(start_idx + 24, len(times))):
            result.append({
                "timestamp": times[idx],
                "temperature": _safe_get(hourly.get("temperature_2m", []), idx),
                "apparent_temperature": _safe_get(hourly.get("apparent_temperature", []), idx),
                "precipitation": _safe_get(hourly.get("precipitation", []), idx),
                "precipitation_probability": _safe_get(hourly.get("precipitation_probability", []), idx),
                "relative_humidity": _validate_humidity(_safe_get(hourly.get("relative_humidity_2m", []), idx)),
                "wind_speed": _safe_get(hourly.get("wind_speed_10m", []), idx),
                "wind_direction": _safe_get(hourly.get("wind_direction_10m", []), idx),
                "weather_code": _safe_get(hourly.get("weather_code", []), idx),
                "evapotranspiration": _safe_get(hourly.get("et0_fao_evapotranspiration", []), idx),
                "rain": None,
                "surface_pressure": None,
            })

        return result

    # ── Daily Forecast ──────────────────────────────────────────────────────

    def fetch_daily(self, latitude: float, longitude: float) -> list:
        """
        Fetch daily forecast for the next 7 days.

        Returns a list of up to 7 dicts matching Weather model fields.
        Each daily record uses noon UTC as the canonical timestamp.
        """
        data = self._make_request(
            latitude,
            longitude,
            {
                "daily": (
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_sum,"
                    "precipitation_probability_max,"
                    "wind_speed_10m_max,"
                    "wind_direction_10m_dominant,"
                    "weather_code,"
                    "sunrise,"
                    "sunset,"
                    "et0_fao_evapotranspiration"
                ),
                "forecast_days": 7,
            },
        )

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            logger.warning("Open-Meteo returned empty 'daily' section.")
            return []

        result = []
        for idx, day in enumerate(dates):
            # Store as noon UTC to avoid date boundary ambiguity
            timestamp = f"{day}T12:00:00"

            # temperature field holds the daily max for daily records;
            # apparent_temperature holds the daily min for daily records.
            result.append({
                "timestamp": timestamp,
                "temperature": _safe_get(daily.get("temperature_2m_max", []), idx),       # max temp
                "apparent_temperature": _safe_get(daily.get("temperature_2m_min", []), idx),  # min temp (reused field)
                "precipitation": _safe_get(daily.get("precipitation_sum", []), idx),
                "precipitation_probability": _safe_get(daily.get("precipitation_probability_max", []), idx),
                "wind_speed": _safe_get(daily.get("wind_speed_10m_max", []), idx),
                "wind_direction": _safe_get(daily.get("wind_direction_10m_dominant", []), idx),
                "weather_code": _safe_get(daily.get("weather_code", []), idx),
                "evapotranspiration": _safe_get(daily.get("et0_fao_evapotranspiration", []), idx),
                "rain": None,
                "relative_humidity": None,
                "surface_pressure": None,
                # Extra daily fields stored as string metadata (not in model, passed through)
                "sunrise": _safe_get(daily.get("sunrise", []), idx),
                "sunset": _safe_get(daily.get("sunset", []), idx),
            })

        return result

    # ── Historical Weather ──────────────────────────────────────────────────

    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def fetch_historical(self, latitude: float, longitude: float, start_date: str, end_date: str) -> list:
        """
        Fetch historical hourly weather data for the given coordinates and date range (YYYY-MM-DD).

        Uses Open-Meteo Historical Archive API (archive-api.open-meteo.com).
        Returns a list of dicts matching Weather model fields.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "UTC",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "hourly": (
                "temperature_2m,"
                "apparent_temperature,"
                "precipitation,"
                "rain,"
                "relative_humidity_2m,"
                "wind_speed_10m,"
                "wind_direction_10m,"
                "surface_pressure,"
                "weather_code,"
                "et0_fao_evapotranspiration"
            ),
        }

        try:
            response = requests.get(self.ARCHIVE_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning(f"Archive API request failed: {exc}, attempting fallback to forecast endpoint.")
            data = self._make_request(latitude, longitude, {
                "start_date": start_date,
                "end_date": end_date,
                "hourly": params["hourly"]
            })

        hourly = data.get("hourly", {})
        timestamps = hourly.get("time", [])
        if not timestamps:
            logger.warning(f"Open-Meteo returned empty historical section for range {start_date} to {end_date}.")
            return []

        result = []
        for idx, ts in enumerate(timestamps):
            result.append({
                "timestamp": ts,
                "temperature": _safe_get(hourly.get("temperature_2m", []), idx),
                "apparent_temperature": _safe_get(hourly.get("apparent_temperature", []), idx),
                "precipitation": _safe_get(hourly.get("precipitation", []), idx),
                "rain": _safe_get(hourly.get("rain", []), idx),
                "relative_humidity": _validate_humidity(_safe_get(hourly.get("relative_humidity_2m", []), idx)),
                "wind_speed": _safe_get(hourly.get("wind_speed_10m", []), idx),
                "wind_direction": _safe_get(hourly.get("wind_direction_10m", []), idx),
                "surface_pressure": _safe_get(hourly.get("surface_pressure", []), idx),
                "weather_code": _safe_get(hourly.get("weather_code", []), idx),
                "evapotranspiration": _safe_get(hourly.get("et0_fao_evapotranspiration", []), idx),
                "precipitation_probability": _safe_get(hourly.get("precipitation_probability", []), idx),
            })

        return result

