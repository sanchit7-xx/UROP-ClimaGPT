"""
Weather App Tests — Stage 2.

Tests cover:
  - API endpoints (current, hourly, daily, refresh)
  - Authentication (unauthenticated → 401)
  - Authorization (another farmer's farm → 404)
  - Provider response parsing (mocked — no real HTTP calls)
  - Caching behavior (cache hit / cache miss)
  - API failure / timeout handling
  - Invalid data validation
  - Response format / structure
  - Refresh endpoint for any farmer (not just staff)

Open-Meteo is always mocked with unittest.mock.patch so tests are fast,
deterministic, and do not depend on any external service.
"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import FarmerProfile
from farms.models import Farm
from weather.models import Weather, ForecastTypeChoices, WeatherSourceChoices
from weather.services.open_meteo_provider import OpenMeteoProvider
from weather.services.weather_service import WeatherService

User = get_user_model()


# ── Shared fixtures ──────────────────────────────────────────────────────────

def make_user(email="farmer@test.com", password="testpass123"):
    return User.objects.create_user(username=email, email=email, password=password)


def make_farmer(user, name="Test Farmer", phone=None):
    if phone is None:
        phone = f"+9198{abs(hash(user.email)) % 100000000:08d}"
    return FarmerProfile.objects.create(
        user=user,
        full_name=name,
        phone_number=phone,
        state="Tamil Nadu",
        district="Chennai",
        village="Mylapore",
    )


def make_farm(farmer, name="Test Farm", lat=13.0827, lon=80.2707):
    return Farm.objects.create(
        farmer=farmer,
        farm_name=name,
        farm_area=5.0,
        farm_area_unit="acre",
        irrigation_type="rain_fed",
        latitude=lat,
        longitude=lon,
    )


# ── Mocked Open-Meteo responses ──────────────────────────────────────────────

MOCK_CURRENT_RESPONSE = {
    "current": {
        "time": "2026-09-22T10:00",
        "temperature_2m": 31.2,
        "apparent_temperature": 34.5,
        "relative_humidity_2m": 72,
        "precipitation": 0.0,
        "rain": 0.0,
        "wind_speed_10m": 14.2,
        "wind_direction_10m": 180,
        "surface_pressure": 1008.4,
        "et0_fao_evapotranspiration": 0.2,
        "weather_code": 1,
    }
}

MOCK_HOURLY_RESPONSE = {
    "hourly": {
        "time": [f"2026-09-22T{h:02d}:00" for h in range(24)] +
                [f"2026-09-23T{h:02d}:00" for h in range(24)],
        "temperature_2m": [28.0 + i * 0.3 for i in range(48)],
        "apparent_temperature": [29.0 + i * 0.2 for i in range(48)],
        "precipitation": [0.0] * 48,
        "precipitation_probability": [10 + i for i in range(48)],
        "relative_humidity_2m": [70.0] * 48,
        "wind_speed_10m": [12.0] * 48,
        "wind_direction_10m": [180.0] * 48,
        "weather_code": [1] * 48,
        "et0_fao_evapotranspiration": [0.1] * 48,
    }
}

MOCK_DAILY_RESPONSE = {
    "daily": {
        "time": [f"2026-09-2{d}" for d in range(2, 9)],
        "temperature_2m_max": [32.0, 33.0, 29.0, 28.0, 30.0, 32.0, 33.0],
        "temperature_2m_min": [25.0, 26.0, 24.0, 23.0, 24.0, 25.0, 26.0],
        "precipitation_sum": [0.0, 2.0, 15.0, 22.0, 5.0, 1.0, 2.0],
        "precipitation_probability_max": [10, 30, 75, 85, 45, 20, 25],
        "wind_speed_10m_max": [20.0] * 7,
        "wind_direction_10m_dominant": [225.0] * 7,
        "weather_code": [1, 3, 61, 63, 45, 1, 2],
        "sunrise": [f"2026-09-2{d}T06:00" for d in range(2, 9)],
        "sunset": [f"2026-09-2{d}T18:00" for d in range(2, 9)],
        "et0_fao_evapotranspiration": [3.2] * 7,
    }
}


# ── Provider Unit Tests ──────────────────────────────────────────────────────

class OpenMeteoProviderParsingTests(TestCase):
    """Unit-tests for OpenMeteoProvider normalisation logic."""

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_current_parses_all_fields(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_CURRENT_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_current(13.0827, 80.2707)

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["temperature"], 31.2)
        self.assertEqual(entry["apparent_temperature"], 34.5)
        self.assertEqual(entry["relative_humidity"], 72)
        self.assertEqual(entry["precipitation"], 0.0)
        self.assertEqual(entry["rain"], 0.0)
        self.assertEqual(entry["wind_speed"], 14.2)
        self.assertEqual(entry["wind_direction"], 180)
        self.assertEqual(entry["surface_pressure"], 1008.4)
        self.assertEqual(entry["evapotranspiration"], 0.2)
        self.assertEqual(entry["weather_code"], 1)
        self.assertTrue(entry["precipitation_probability"] is None or isinstance(entry["precipitation_probability"], (int, float)))
        self.assertEqual(entry["timestamp"], "2026-09-22T10:00")

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_current_empty_response_returns_empty_list(self, mock_get):
        mock_get.return_value.json.return_value = {"current": {}}
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_current(13.0827, 80.2707)
        self.assertEqual(result, [])

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_hourly_returns_up_to_24_entries(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_HOURLY_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_hourly(13.0827, 80.2707)

        self.assertLessEqual(len(result), 24)
        self.assertGreater(len(result), 0)

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_hourly_has_precipitation_probability(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_HOURLY_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_hourly(13.0827, 80.2707)
        self.assertTrue(any(r["precipitation_probability"] is not None for r in result))

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_daily_returns_7_days(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_DAILY_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_daily(13.0827, 80.2707)
        self.assertEqual(len(result), 7)

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_daily_has_temperature_max_min(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_DAILY_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        provider = OpenMeteoProvider()
        result = provider.fetch_daily(13.0827, 80.2707)
        self.assertEqual(result[0]["temperature"], 32.0)        # max
        self.assertEqual(result[0]["apparent_temperature"], 25.0)  # min

    def test_invalid_humidity_rejected(self):
        from weather.services.open_meteo_provider import _validate_humidity
        self.assertIsNone(_validate_humidity(150))   # out of range
        self.assertIsNone(_validate_humidity(-5))    # negative
        self.assertEqual(_validate_humidity(72), 72)
        self.assertEqual(_validate_humidity(0), 0)
        self.assertEqual(_validate_humidity(100), 100)
        self.assertIsNone(_validate_humidity(None))

    @patch("weather.services.open_meteo_provider.requests.get")
    def test_fetch_current_api_failure_raises(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.Timeout("timed out")

        provider = OpenMeteoProvider()
        with self.assertRaises(req_lib.Timeout):
            provider.fetch_current(13.0827, 80.2707)


# ── API Endpoint Tests ───────────────────────────────────────────────────────

class WeatherAPIBaseTestCase(TestCase):
    """Base class providing authenticated user + farm fixtures."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Farmer A
        self.user_a = make_user("farmer_a@test.com")
        self.farmer_a = make_farmer(self.user_a, "Farmer A")
        self.farm_a = make_farm(self.farmer_a, "Farm A")
        self.token_a = Token.objects.create(user=self.user_a)

        # Farmer B (for cross-access tests)
        self.user_b = make_user("farmer_b@test.com")
        self.farmer_b = make_farmer(self.user_b, "Farmer B")
        self.farm_b = make_farm(self.farmer_b, "Farm B", lat=19.0760, lon=72.8777)
        self.token_b = Token.objects.create(user=self.user_b)

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _create_weather(self, farm, forecast_type, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return Weather.objects.create(
            farm=farm,
            timestamp=timestamp,
            temperature=31.2,
            apparent_temperature=34.5,
            relative_humidity=72.0,
            precipitation=0.0,
            rain=0.0,
            wind_speed=14.2,
            wind_direction=180.0,
            surface_pressure=1008.4,
            evapotranspiration=0.2,
            precipitation_probability=10.0,
            weather_code=1,
            source=WeatherSourceChoices.OPEN_METEO,
            forecast_type=forecast_type,
        )


class AuthenticationTests(WeatherAPIBaseTestCase):

    def test_current_weather_requires_auth(self):
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_hourly_requires_auth(self):
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/hourly/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_daily_requires_auth(self):
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/daily/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_requires_auth(self):
        response = self.client.post(f"/api/weather/farms/{self.farm_a.id}/refresh/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthorizationTests(WeatherAPIBaseTestCase):

    def test_farmer_cannot_access_other_farmers_current_weather(self):
        self.authenticate(self.token_b)
        # Farmer B tries to access Farm A's weather
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_farmer_cannot_access_other_farmers_hourly(self):
        self.authenticate(self.token_b)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/hourly/")
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_farmer_cannot_access_other_farmers_daily(self):
        self.authenticate(self.token_b)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/daily/")
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_farmer_cannot_refresh_other_farmers_farm(self):
        self.authenticate(self.token_b)
        response = self.client.post(f"/api/weather/farms/{self.farm_a.id}/refresh/")
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])


class CurrentWeatherEndpointTests(WeatherAPIBaseTestCase):

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_current_weather_returns_correct_structure(self, mock_factory):
        mock_provider = MagicMock()
        mock_provider.fetch_current.return_value = [{
            "timestamp": "2026-09-22T10:00",
            "temperature": 31.2,
            "apparent_temperature": 34.5,
            "relative_humidity": 72,
            "precipitation": 0.0,
            "rain": 0.0,
            "wind_speed": 14.2,
            "wind_direction": 180,
            "surface_pressure": 1008.4,
            "evapotranspiration": 0.2,
            "weather_code": 1,
            "precipitation_probability": None,
        }]
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("farm_id", data)
        self.assertIn("location", data)
        self.assertIn("results", data)
        self.assertEqual(data["farm_id"], self.farm_a.id)
        self.assertIn("latitude", data["location"])
        self.assertIn("longitude", data["location"])
        self.assertGreater(len(data["results"]), 0)
        self.assertEqual(data["results"][0]["temperature"], 31.2)

    def test_current_weather_404_when_no_data_in_db_and_provider_fails(self):
        """When provider returns empty list and no DB records, return 404."""
        self.authenticate(self.token_a)
        with patch("weather.services.weather_service.WeatherProviderFactory.get_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_provider.fetch_current.return_value = []
            mock_factory.return_value = mock_provider
            response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_current_weather_returns_weather_code_field(self):
        """Verify weather_code is present in response (needed by frontend for icons)."""
        self._create_weather(self.farm_a, ForecastTypeChoices.CURRENT)
        # Inject into cache to avoid provider call
        cache.set(
            f"weather:{self.farm_a.id}:{ForecastTypeChoices.CURRENT}",
            list(Weather.objects.filter(farm=self.farm_a, forecast_type=ForecastTypeChoices.CURRENT)),
        )
        self.authenticate(self.token_a)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("weather_code", response.json()["results"][0])

    def test_current_weather_503_on_provider_exception(self):
        """Provider exception → 503 Service Unavailable."""
        self.authenticate(self.token_a)
        with patch("weather.services.weather_service.WeatherProviderFactory.get_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_provider.fetch_current.side_effect = Exception("Connection refused")
            mock_factory.return_value = mock_provider
            response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class HourlyForecastEndpointTests(WeatherAPIBaseTestCase):

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_hourly_returns_up_to_24_entries(self, mock_factory):
        mock_provider = MagicMock()
        mock_provider.fetch_hourly.return_value = [
            {
                "timestamp": f"2026-09-22T{h:02d}:00",
                "temperature": 28.0 + h * 0.3,
                "apparent_temperature": 29.0,
                "precipitation": 0.0,
                "precipitation_probability": 10.0,
                "relative_humidity": 70.0,
                "wind_speed": 12.0,
                "wind_direction": 180.0,
                "weather_code": 1,
                "evapotranspiration": 0.1,
                "rain": None,
                "surface_pressure": None,
            }
            for h in range(24)
        ]
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/hourly/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data["results"]), 24)

    def test_hourly_uses_cache(self):
        """If cache has data, provider should NOT be called."""
        cached_records = [self._create_weather(self.farm_a, ForecastTypeChoices.HOURLY)]
        cache.set(f"weather:{self.farm_a.id}:{ForecastTypeChoices.HOURLY}", cached_records, 3600)

        self.authenticate(self.token_a)
        with patch("weather.services.weather_service.WeatherProviderFactory.get_provider") as mock_factory:
            response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/hourly/")
            mock_factory.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DailyForecastEndpointTests(WeatherAPIBaseTestCase):

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_daily_returns_7_days(self, mock_factory):
        mock_provider = MagicMock()
        mock_provider.fetch_daily.return_value = [
            {
                "timestamp": f"2026-09-2{d}T12:00:00",
                "temperature": 32.0,
                "apparent_temperature": 25.0,
                "precipitation": 0.0,
                "precipitation_probability": 10.0,
                "wind_speed": 20.0,
                "wind_direction": 225.0,
                "weather_code": 1,
                "evapotranspiration": 3.2,
                "rain": None,
                "relative_humidity": None,
                "surface_pressure": None,
                "sunrise": f"2026-09-2{d}T06:00",
                "sunset": f"2026-09-2{d}T18:00",
            }
            for d in range(2, 9)
        ]
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/daily/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 7)


class RefreshEndpointTests(WeatherAPIBaseTestCase):

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_refresh_works_for_normal_farmer(self, mock_factory):
        """Any authenticated farmer can refresh their own farm — not staff-only."""
        mock_provider = MagicMock()
        mock_provider.fetch_current.return_value = [{
            "timestamp": "2026-09-22T10:00",
            "temperature": 31.2,
            "apparent_temperature": 34.5,
            "relative_humidity": 72,
            "precipitation": 0.0, "rain": 0.0,
            "wind_speed": 14.2, "wind_direction": 180,
            "surface_pressure": 1008.4, "evapotranspiration": 0.2,
            "weather_code": 1, "precipitation_probability": None,
        }]
        mock_provider.fetch_hourly.return_value = []
        mock_provider.fetch_daily.return_value = []
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.post(f"/api/weather/farms/{self.farm_a.id}/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("refreshed successfully", data["detail"])

    def test_refresh_clears_cache(self):
        """After refresh, old cache should be invalidated."""
        old_cache_key = f"weather:{self.farm_a.id}:{ForecastTypeChoices.CURRENT}"
        cache.set(old_cache_key, ["old_data"], 3600)

        with patch("weather.services.weather_service.WeatherProviderFactory.get_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_provider.fetch_current.return_value = []
            mock_provider.fetch_hourly.return_value = []
            mock_provider.fetch_daily.return_value = []
            mock_factory.return_value = mock_provider

            self.authenticate(self.token_a)
            self.client.post(f"/api/weather/farms/{self.farm_a.id}/refresh/")
            # Provider must have been called (cache was cleared)
            mock_provider.fetch_current.assert_called_once()

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_refresh_503_on_provider_error(self, mock_factory):
        mock_provider = MagicMock()
        mock_provider.fetch_current.side_effect = Exception("API down")
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.post(f"/api/weather/farms/{self.farm_a.id}/refresh/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class DuplicatePreventionTests(WeatherAPIBaseTestCase):

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_update_or_create_prevents_duplicates(self, mock_factory):
        """Calling _fetch_and_store twice for same timestamp should not duplicate records."""
        ts = "2026-09-22T10:00"
        entry = {
            "timestamp": ts,
            "temperature": 31.2,
            "apparent_temperature": 34.5,
            "relative_humidity": 72,
            "precipitation": 0.0, "rain": 0.0,
            "wind_speed": 14.2, "wind_direction": 180,
            "surface_pressure": 1008.4, "evapotranspiration": 0.2,
            "weather_code": 1, "precipitation_probability": None,
        }
        mock_provider = MagicMock()
        mock_provider.fetch_current.return_value = [entry]
        mock_factory.return_value = mock_provider

        WeatherService._fetch_and_store(self.farm_a, ForecastTypeChoices.CURRENT)
        WeatherService._fetch_and_store(self.farm_a, ForecastTypeChoices.CURRENT)

        count = Weather.objects.filter(
            farm=self.farm_a,
            forecast_type=ForecastTypeChoices.CURRENT,
        ).count()
        self.assertEqual(count, 1)


class ResponseFormatTests(WeatherAPIBaseTestCase):
    """Ensure API response envelope matches the documented format."""

    @patch("weather.services.weather_service.WeatherProviderFactory.get_provider")
    def test_response_has_all_required_keys(self, mock_factory):
        mock_provider = MagicMock()
        mock_provider.fetch_current.return_value = [{
            "timestamp": "2026-09-22T10:00",
            "temperature": 31.2, "apparent_temperature": 34.5,
            "relative_humidity": 72, "precipitation": 0.0, "rain": 0.0,
            "wind_speed": 14.2, "wind_direction": 180,
            "surface_pressure": 1008.4, "evapotranspiration": 0.2,
            "weather_code": 1, "precipitation_probability": None,
        }]
        mock_factory.return_value = mock_provider

        self.authenticate(self.token_a)
        response = self.client.get(f"/api/weather/farms/{self.farm_a.id}/current/")
        data = response.json()

        required_keys = ["farm_id", "location", "source", "forecast_type", "count", "results"]
        for key in required_keys:
            self.assertIn(key, data, f"Missing key '{key}' in response")

        location_keys = ["latitude", "longitude", "name", "state"]
        for key in location_keys:
            self.assertIn(key, data["location"], f"Missing location key '{key}'")

        result_fields = ["temperature", "apparent_temperature", "relative_humidity",
                         "wind_speed", "wind_direction", "surface_pressure",
                         "precipitation", "weather_code", "timestamp"]
        for field in result_fields:
            self.assertIn(field, data["results"][0], f"Missing result field '{field}'")


# ── Stage 3 Historical Weather & Data Pipeline Tests ─────────────────────────

class Stage3HistoricalPipelineTests(WeatherAPIBaseTestCase):

    def test_validator_rejects_invalid_values(self):
        from weather.pipeline.validator import HistoricalWeatherValidator
        validator = HistoricalWeatherValidator()

        valid_entry = {
            "timestamp": "2026-09-01T10:00:00Z",
            "latitude": 12.82, "longitude": 80.03,
            "temperature": 30.5, "relative_humidity": 70.0,
            "precipitation": 0.0, "wind_speed": 10.0, "surface_pressure": 1005.0
        }
        invalid_temp = dict(valid_entry, temperature=150.0)
        invalid_hum = dict(valid_entry, relative_humidity=-20.0)

        valid_list, invalid_list = validator.validate([valid_entry, invalid_temp, invalid_hum])
        self.assertEqual(len(valid_list), 1)
        self.assertEqual(len(invalid_list), 2)

    def test_cleaner_deduplicates_and_flags_gaps(self):
        from weather.pipeline.cleaner import HistoricalWeatherCleaner
        cleaner = HistoricalWeatherCleaner(expected_interval_hours=1.0)

        r1 = {"farm_id": self.farm_a.id, "timestamp": "2026-09-01T10:00:00Z", "temperature": 30.0}
        r2 = {"farm_id": self.farm_a.id, "timestamp": "2026-09-01T10:00:00Z", "temperature": 30.0}  # duplicate
        r3 = {"farm_id": self.farm_a.id, "timestamp": "2026-09-01T13:00:00Z", "temperature": 48.0}  # gap (2h gap) + outlier (48C)

        cleaned, stats = cleaner.clean([r1, r2, r3])
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(stats["duplicates_removed"], 1)
        self.assertGreaterEqual(stats["missing_gaps_detected"], 1)
        self.assertEqual(stats["outliers_flagged"], 1)

    def test_dataset_builder_csv_export(self):
        from weather.pipeline.dataset_builder import HistoricalDatasetBuilder
        builder = HistoricalDatasetBuilder()

        records = [{
            "timestamp": "2026-09-01T10:00:00Z",
            "farm_id": self.farm_a.id,
            "latitude": 12.8223, "longitude": 80.0272,
            "temperature": 31.0, "apparent_temperature": 34.0,
            "precipitation": 0.0, "rain": 0.0, "relative_humidity": 70.0,
            "wind_speed": 12.0, "wind_direction": 180.0,
            "surface_pressure": 1008.0, "evapotranspiration": 0.2,
            "weather_code": 1, "source": "OPEN_METEO"
        }]
        csv_str = builder.to_csv(records)
        self.assertIn("timestamp,farm_id,latitude,longitude,temperature", csv_str)
        self.assertIn("2026-09-01T10:00:00Z", csv_str)

    @patch("weather.services.historical_weather_service.HistoricalWeatherCollector.collect")
    def test_historical_service_collect_and_summary(self, mock_collect):
        from weather.services.historical_weather_service import HistoricalWeatherService
        mock_collect.return_value = [
            {
                "timestamp": f"2026-09-01T{h:02d}:00:00Z",
                "temperature": 25.0 + h,
                "apparent_temperature": 27.0 + h,
                "relative_humidity": 60.0,
                "precipitation": 1.0,
                "rain": 1.0,
                "wind_speed": 10.0,
                "wind_direction": 180.0,
                "surface_pressure": 1008.0,
                "evapotranspiration": 0.1,
                "weather_code": 1,
            }
            for h in range(5)
        ]

        records = HistoricalWeatherService.get_historical_weather(self.farm_a, "2026-09-01", "2026-09-01", force_collect=True)
        self.assertEqual(len(records), 5)

        summary = HistoricalWeatherService.get_historical_summary(self.farm_a, "2026-09-01", "2026-09-01")
        self.assertEqual(summary["record_count"], 5)
        self.assertEqual(summary["total_precipitation"], 5.0)
        self.assertEqual(summary["min_temperature"], 25.0)
        self.assertEqual(summary["max_temperature"], 29.0)

    @patch("weather.services.historical_weather_service.HistoricalWeatherCollector.collect")
    def test_historical_weather_api_views(self, mock_collect):
        mock_collect.return_value = [{
            "timestamp": "2026-09-01T10:00:00Z",
            "temperature": 30.0, "apparent_temperature": 32.0,
            "relative_humidity": 65.0, "precipitation": 0.0, "rain": 0.0,
            "wind_speed": 10.0, "wind_direction": 180.0,
            "surface_pressure": 1005.0, "evapotranspiration": 0.2,
            "weather_code": 1,
        }]

        self.authenticate(self.token_a)

        # GET Historical Weather
        res = self.client.get(f"/api/weather/farms/{self.farm_a.id}/historical/?start_date=2026-09-01&end_date=2026-09-01")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)

        # GET Summary
        res_sum = self.client.get(f"/api/weather/farms/{self.farm_a.id}/historical/summary/?start_date=2026-09-01&end_date=2026-09-01")
        self.assertEqual(res_sum.status_code, 200)
        self.assertEqual(res_sum.json()["record_count"], 1)

        # GET Export CSV
        res_exp = self.client.get(f"/api/weather/farms/{self.farm_a.id}/historical/export/?start_date=2026-09-01&end_date=2026-09-01&format=csv")
        self.assertEqual(res_exp.status_code, 200)
        self.assertEqual(res_exp["Content-Type"], "text/csv")

    def test_farm_ownership_enforcement_for_historical_api(self):
        """Farmer B cannot access Farmer A's historical weather."""
        self.authenticate(self.token_b)
        res = self.client.get(f"/api/weather/farms/{self.farm_a.id}/historical/?start_date=2026-09-01&end_date=2026-09-01")
        self.assertEqual(res.status_code, 404)

    def test_invalid_date_range_rejected(self):
        self.authenticate(self.token_a)
        res = self.client.get(f"/api/weather/farms/{self.farm_a.id}/historical/?start_date=2026-09-10&end_date=2026-09-01")
        self.assertEqual(res.status_code, 400)
        self.assertIn("start_date", res.json()["detail"])

