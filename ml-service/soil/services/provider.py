"""
soil/services/provider.py

Base interface for Soil Moisture Providers.
Follows the same provider pattern established in Stage 2 (WeatherProvider).
"""
from abc import ABC, abstractmethod


class SoilMoistureProvider(ABC):
    """
    Abstract base class for all soil moisture providers.

    Subclasses implement source-specific retrieval and normalization
    (e.g., SENSOR, SATELLITE, REANALYSIS, ESTIMATED).
    """

    @abstractmethod
    def get_current(self, farm, depth=None):
        """
        Return the latest valid SoilMoisture record for the farm, or None.
        """
        pass

    @abstractmethod
    def get_history(self, farm, start_date=None, end_date=None, depth=None):
        """
        Return historical SoilMoisture records for the farm matching filters.
        """
        pass
