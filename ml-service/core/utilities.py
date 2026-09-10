"""
core/utilities.py

Shared utilities for ClimaGPT:
  - Coordinate validators
  - MapboxService — reverse geocoding (lat/lng → address components)

Architecture notes:
  - MapboxService is a plain Python class, NOT a Django model or DRF view.
  - It reads MAPBOX_ACCESS_TOKEN from Django settings (which reads from .env).
  - Stage 2 can make this async by wrapping calls in asyncio / Celery tasks.
  - Views call this service; models never call it directly.
"""
import logging

import requests
from django.conf import settings

from .exceptions import InvalidCoordinatesError, MapboxServiceError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coordinate validators
# ---------------------------------------------------------------------------

def validate_latitude(value) -> float:
    """
    Ensure *value* is a valid latitude (−90 … +90).

    Raises:
        InvalidCoordinatesError
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise InvalidCoordinatesError('Latitude must be a numeric value.')
    if not (-90.0 <= value <= 90.0):
        raise InvalidCoordinatesError(
            f'Latitude {value} is out of range. Must be between -90 and 90.'
        )
    return value


def validate_longitude(value) -> float:
    """
    Ensure *value* is a valid longitude (−180 … +180).

    Raises:
        InvalidCoordinatesError
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise InvalidCoordinatesError('Longitude must be a numeric value.')
    if not (-180.0 <= value <= 180.0):
        raise InvalidCoordinatesError(
            f'Longitude {value} is out of range. Must be between -180 and 180.'
        )
    return value


# ---------------------------------------------------------------------------
# Mapbox Service
# ---------------------------------------------------------------------------

class MapboxService:
    """
    Encapsulates all interactions with the Mapbox REST API.

    Stage 1 provides:
        reverse_geocode(latitude, longitude) → dict of address components

    Future stages can add:
        forward_geocode(query)      — place name → coordinates
        isochrone(lat, lng, mins)   — reachability polygon
        etc.

    Usage:
        service = MapboxService()
        address = service.reverse_geocode(18.5204, 73.8567)
        # → {"locality": "Hadapsar", "city": "Pune", "state": "Maharashtra", ...}

    Errors:
        MapboxServiceError      — API / network problems
        InvalidCoordinatesError — bad coordinates (raised before HTTP call)
    """

    _GEOCODING_URL = (
        'https://api.mapbox.com/geocoding/v5/mapbox.places/{lng},{lat}.json'
    )

    def __init__(self):
        self.access_token: str = settings.MAPBOX_ACCESS_TOKEN
        self.timeout: int = getattr(settings, 'MAPBOX_REQUEST_TIMEOUT', 10)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reverse_geocode(self, latitude, longitude) -> dict:
        """
        Convert GPS coordinates to human-readable address components.

        Args:
            latitude:  float-compatible, −90 to +90
            longitude: float-compatible, −180 to +180

        Returns:
            dict with keys:
                locality, village, city, district, state, country, postal_code
            Values are empty strings when Mapbox has no data for that component.

        Raises:
            InvalidCoordinatesError — coordinates out of range
            MapboxServiceError      — API/network failure
        """
        latitude = validate_latitude(latitude)
        longitude = validate_longitude(longitude)

        if not self.access_token:
            logger.warning('MAPBOX_ACCESS_TOKEN is not configured.')
            raise MapboxServiceError(
                'Mapbox access token is not configured. '
                'Set MAPBOX_ACCESS_TOKEN in your .env file.'
            )

        url = self._GEOCODING_URL.format(lat=latitude, lng=longitude)
        params = {
            'access_token': self.access_token,
            'types': ','.join([
                'country', 'region', 'district',
                'locality', 'place', 'postcode', 'neighborhood',
            ]),
            'limit': 5,
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error('Mapbox request timed out for (%s, %s).', latitude, longitude)
            raise MapboxServiceError(
                'Mapbox geocoding service timed out. Please try again later.'
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error('Mapbox network error: %s', exc)
            raise MapboxServiceError(
                'Unable to connect to Mapbox service. Check your network connection.'
            )
        except requests.exceptions.HTTPError as exc:
            logger.error('Mapbox HTTP error: %s', exc)
            raise MapboxServiceError(f'Mapbox service returned an error: {exc}')

        data = response.json()
        features = data.get('features', [])

        if not features:
            logger.info(
                'Mapbox returned no results for coordinates (%s, %s).',
                latitude, longitude,
            )
            return self._empty_address()

        return self._parse_features(features)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_address() -> dict:
        """Return a blank address dict so callers always get the same keys."""
        return {
            'locality': '',
            'village': '',
            'city': '',
            'district': '',
            'state': '',
            'country': '',
            'postal_code': '',
        }

    @staticmethod
    def _parse_features(features: list) -> dict:
        """
        Walk the Mapbox feature list (most-specific first) and populate
        address components by matching place_type identifiers.

        Mapbox places the most-specific result first, so we iterate all
        features and fill in any components we haven't seen yet.
        """
        address = MapboxService._empty_address()

        for feature in features:
            place_types = feature.get('place_type', [])
            text = feature.get('text', '')
            context = feature.get('context', [])

            # Component from the feature itself
            if 'neighborhood' in place_types or 'locality' in place_types:
                address['locality'] = address['locality'] or text
                address['village'] = address['village'] or text
            elif 'place' in place_types:
                address['city'] = address['city'] or text
            elif 'district' in place_types:
                address['district'] = address['district'] or text
            elif 'region' in place_types:
                address['state'] = address['state'] or text
            elif 'country' in place_types:
                address['country'] = address['country'] or text
            elif 'postcode' in place_types:
                address['postal_code'] = address['postal_code'] or text

            # Additional components from the context array
            for ctx in context:
                ctx_id: str = ctx.get('id', '')
                ctx_text: str = ctx.get('text', '')

                if ctx_id.startswith(('neighborhood', 'locality')):
                    address['locality'] = address['locality'] or ctx_text
                elif ctx_id.startswith('place'):
                    address['city'] = address['city'] or ctx_text
                elif ctx_id.startswith('district'):
                    address['district'] = address['district'] or ctx_text
                elif ctx_id.startswith('region'):
                    address['state'] = address['state'] or ctx_text
                elif ctx_id.startswith('country'):
                    address['country'] = address['country'] or ctx_text
                elif ctx_id.startswith('postcode'):
                    address['postal_code'] = address['postal_code'] or ctx_text

        return address
