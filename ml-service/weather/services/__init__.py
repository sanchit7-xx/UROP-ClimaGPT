import requests
from django.conf import settings
from .provider import WeatherProvider
from .open_meteo_provider import OpenMeteoProvider

class WeatherProviderFactory:
    """Factory to get the appropriate weather provider based on settings."""
    @staticmethod
    def get_provider() -> WeatherProvider:
        provider_name = settings.WEATHER_PROVIDER.upper()
        if provider_name == 'OPEN_METEO':
            return OpenMeteoProvider()
        # Placeholder for future providers
        raise NotImplementedError(f"Weather provider '{provider_name}' is not implemented.")
