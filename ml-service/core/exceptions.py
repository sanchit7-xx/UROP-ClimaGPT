"""
core/exceptions.py

Custom exception classes and a DRF exception handler that produces
consistent JSON error responses across all ClimaGPT endpoints.

Response format:
    {
        "error": "<human-readable title>",
        "details": "<message or dict of field errors>"
    }
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


# ---------------------------------------------------------------------------
# ClimaGPT domain exceptions
# ---------------------------------------------------------------------------

class ClimaGPTException(Exception):
    """Base exception for all ClimaGPT domain errors."""


class UnauthorizedFarmAccess(ClimaGPTException):
    """Raised when a farmer tries to access another farmer's farm."""


class UnauthorizedCropAccess(ClimaGPTException):
    """Raised when a farmer tries to access another farmer's crop."""


class InvalidCoordinatesError(ClimaGPTException):
    """Raised when latitude or longitude values are out of valid range."""


class MapboxServiceError(ClimaGPTException):
    """
    Raised when the Mapbox reverse geocoding service returns an error,
    times out, or is unreachable.
    """


# ---------------------------------------------------------------------------
# DRF custom exception handler
# ---------------------------------------------------------------------------

def custom_exception_handler(exc, context):
    """
    Intercepts all exceptions raised inside DRF views and formats them
    into the ClimaGPT standard error shape:

        {"error": "...", "details": "..."}

    Falls through to DRF's default handler for unrecognised exceptions
    so that standard HTTP errors (404, 405, etc.) are also reformatted.
    """
    # Let DRF process its own exceptions first (ValidationError, NotFound, …)
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            'error': _status_title(response.status_code),
            'details': _flatten(response.data),
        }
        return response

    # Handle our custom domain exceptions
    if isinstance(exc, UnauthorizedFarmAccess):
        return Response(
            {
                'error': 'Unauthorized',
                'details': str(exc) or 'You do not have permission to access this farm.',
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, UnauthorizedCropAccess):
        return Response(
            {
                'error': 'Unauthorized',
                'details': str(exc) or 'You do not have permission to access this crop.',
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, InvalidCoordinatesError):
        return Response(
            {'error': 'Invalid coordinates', 'details': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, MapboxServiceError):
        return Response(
            {'error': 'Geocoding service error', 'details': str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # Unknown exception — return None so Django's 500 handler takes over.
    # Do NOT expose raw tracebacks to clients.
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _status_title(code: int) -> str:
    """Map HTTP status code → human-readable error title."""
    _titles = {
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        409: 'Conflict',
        422: 'Unprocessable Entity',
        429: 'Too Many Requests',
        500: 'Internal Server Error',
        503: 'Service Unavailable',
    }
    return _titles.get(code, 'Error')


def _flatten(data):
    """
    Reduce DRF's nested error structures to a simpler string or dict
    so that clients receive something easy to display.
    """
    if isinstance(data, dict):
        # DRF validation errors: {'field': ['message']}
        if 'detail' in data:
            return str(data['detail'])
        return {
            k: (v[0] if isinstance(v, list) and len(v) == 1 else v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return data[0] if len(data) == 1 else data
    return str(data)
