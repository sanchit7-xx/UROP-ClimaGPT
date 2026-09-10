"""
core/tests.py

Tests for:
  - Health endpoint (public, no auth required)
  - MapboxService (all branches mocked — no real HTTP calls)
"""
from unittest.mock import MagicMock, patch

import requests as req_lib
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import InvalidCoordinatesError, MapboxServiceError
from core.utilities import MapboxService, validate_latitude, validate_longitude

HEALTH_URL = '/api/health/'


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class HealthEndpointTestCase(APITestCase):

    def test_returns_200(self):
        response = self.client.get(HEALTH_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_correct_body(self):
        response = self.client.get(HEALTH_URL)
        self.assertEqual(response.data['service'], 'ClimaGPT Django Service')
        self.assertEqual(response.data['status'], 'healthy')

    def test_is_publicly_accessible_without_token(self):
        """Health check must not require authentication."""
        self.client.credentials()  # no token
        response = self.client.get(HEALTH_URL)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Coordinate validators
# ---------------------------------------------------------------------------

class CoordinateValidatorTestCase(TestCase):

    def test_valid_latitude(self):
        self.assertEqual(validate_latitude(18.5204), 18.5204)
        self.assertEqual(validate_latitude(-90), -90.0)
        self.assertEqual(validate_latitude(90), 90.0)

    def test_latitude_too_high(self):
        with self.assertRaises(InvalidCoordinatesError):
            validate_latitude(90.001)

    def test_latitude_too_low(self):
        with self.assertRaises(InvalidCoordinatesError):
            validate_latitude(-90.001)

    def test_latitude_not_numeric(self):
        with self.assertRaises(InvalidCoordinatesError):
            validate_latitude('not-a-number')

    def test_valid_longitude(self):
        self.assertEqual(validate_longitude(73.8567), 73.8567)
        self.assertEqual(validate_longitude(-180), -180.0)
        self.assertEqual(validate_longitude(180), 180.0)

    def test_longitude_too_high(self):
        with self.assertRaises(InvalidCoordinatesError):
            validate_longitude(180.001)

    def test_longitude_too_low(self):
        with self.assertRaises(InvalidCoordinatesError):
            validate_longitude(-180.001)


# ---------------------------------------------------------------------------
# MapboxService — all tests use mocks (no real HTTP calls)
# ---------------------------------------------------------------------------

class MapboxServiceTestCase(TestCase):

    def setUp(self):
        self.service = MapboxService()
        self.service.access_token = 'test_token_12345'

    # ── Helper ───────────────────────────────────────────────────────────

    @staticmethod
    def _mock_response(features):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'features': features}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    # ── Success path ─────────────────────────────────────────────────────

    @patch('core.utilities.requests.get')
    def test_reverse_geocode_success(self, mock_get):
        mock_get.return_value = self._mock_response([
            {
                'place_type': ['neighborhood'],
                'text': 'Hadapsar',
                'context': [
                    {'id': 'place.123', 'text': 'Pune'},
                    {'id': 'district.456', 'text': 'Pune District'},
                    {'id': 'region.789', 'text': 'Maharashtra'},
                    {'id': 'country.000', 'text': 'India'},
                    {'id': 'postcode.111', 'text': '411028'},
                ],
            }
        ])
        result = self.service.reverse_geocode(18.5204, 73.8567)

        self.assertEqual(result['locality'], 'Hadapsar')
        self.assertEqual(result['city'], 'Pune')
        self.assertEqual(result['district'], 'Pune District')
        self.assertEqual(result['state'], 'Maharashtra')
        self.assertEqual(result['country'], 'India')
        self.assertEqual(result['postal_code'], '411028')

    @patch('core.utilities.requests.get')
    def test_reverse_geocode_empty_result_returns_blank_dict(self, mock_get):
        mock_get.return_value = self._mock_response([])
        result = self.service.reverse_geocode(18.5204, 73.8567)

        for key in ('locality', 'village', 'city', 'district', 'state', 'country', 'postal_code'):
            self.assertEqual(result[key], '', f'Expected blank string for key "{key}"')

    # ── Error paths ──────────────────────────────────────────────────────

    def test_raises_when_no_token(self):
        self.service.access_token = ''
        with self.assertRaises(MapboxServiceError) as ctx:
            self.service.reverse_geocode(18.5204, 73.8567)
        self.assertIn('access token', str(ctx.exception).lower())

    def test_raises_invalid_latitude(self):
        with self.assertRaises(InvalidCoordinatesError):
            self.service.reverse_geocode(95.0, 73.8567)

    def test_raises_invalid_longitude(self):
        with self.assertRaises(InvalidCoordinatesError):
            self.service.reverse_geocode(18.5204, 185.0)

    @patch('core.utilities.requests.get')
    def test_raises_on_timeout(self, mock_get):
        mock_get.side_effect = req_lib.exceptions.Timeout
        with self.assertRaises(MapboxServiceError) as ctx:
            self.service.reverse_geocode(18.5204, 73.8567)
        self.assertIn('timed out', str(ctx.exception).lower())

    @patch('core.utilities.requests.get')
    def test_raises_on_network_error(self, mock_get):
        mock_get.side_effect = req_lib.exceptions.ConnectionError('DNS failure')
        with self.assertRaises(MapboxServiceError) as ctx:
            self.service.reverse_geocode(18.5204, 73.8567)
        self.assertIn('connect', str(ctx.exception).lower())

    @patch('core.utilities.requests.get')
    def test_raises_on_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            '403 Forbidden'
        )
        mock_get.return_value = mock_resp
        with self.assertRaises(MapboxServiceError):
            self.service.reverse_geocode(18.5204, 73.8567)

    @patch('core.utilities.requests.get')
    def test_uses_correct_url_format(self, mock_get):
        """Latitude and longitude must be in the correct order in the URL."""
        mock_get.return_value = self._mock_response([])
        self.service.reverse_geocode(18.5204, 73.8567)

        call_args = mock_get.call_args
        called_url = call_args[0][0]
        # Mapbox expects {lng},{lat}
        self.assertIn('73.8567,18.5204', called_url)
