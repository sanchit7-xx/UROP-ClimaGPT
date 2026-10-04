"""
soil/services/factory.py

Factory to resolve SoilMoistureProvider instances based on data source.
"""
from soil.models import SoilMoistureSourceChoices
from .provider import SoilMoistureProvider
from .sensor_provider import SensorSoilMoistureProvider
from .satellite_provider import SatelliteSoilMoistureProvider
from .reanalysis_provider import ReanalysisSoilMoistureProvider
from .estimated_provider import EstimatedSoilMoistureProvider


class SoilMoistureProviderFactory:
    """
    Factory creating the appropriate SoilMoistureProvider implementation.
    """

    _providers = {
        SoilMoistureSourceChoices.SENSOR: SensorSoilMoistureProvider,
        SoilMoistureSourceChoices.SATELLITE: SatelliteSoilMoistureProvider,
        SoilMoistureSourceChoices.REANALYSIS: ReanalysisSoilMoistureProvider,
        SoilMoistureSourceChoices.ESTIMATED: EstimatedSoilMoistureProvider,
    }

    @classmethod
    def get_provider(cls, source: str = SoilMoistureSourceChoices.SENSOR) -> SoilMoistureProvider:
        """
        Return an instance of the provider matching the specified source choice.
        Defaults to SensorSoilMoistureProvider.
        """
        provider_cls = cls._providers.get(source, SensorSoilMoistureProvider)
        return provider_cls()
