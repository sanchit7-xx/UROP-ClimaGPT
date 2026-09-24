"""Base class for weather providers.

Implementations must provide methods to fetch current weather, hourly forecast, and daily forecast.
"""

from abc import ABC, abstractmethod
from typing import List, Dict

class WeatherProvider(ABC):
    @abstractmethod
    def fetch_current(self, latitude: float, longitude: float) -> List[Dict]:
        """Return a list of weather data points for the current weather."""
        pass

    @abstractmethod
    def fetch_hourly(self, latitude: float, longitude: float) -> List[Dict]:
        """Return a list of hourly forecast data points (next 24h)."""
        pass

    @abstractmethod
    def fetch_daily(self, latitude: float, longitude: float) -> List[Dict]:
        """Return a list of daily forecast data points (next 7 days)."""
        pass

    @abstractmethod
    def fetch_historical(self, latitude: float, longitude: float, start_date: str, end_date: str) -> List[Dict]:
        """Return a list of historical weather data points for the given date range."""
        pass
