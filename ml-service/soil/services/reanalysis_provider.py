"""
soil/services/reanalysis_provider.py

Prepared architecture for Reanalysis Soil Moisture Products (e.g., ECMWF ERA5-Land).
Stage 4 prepares the service interface without faking external network endpoints.
"""
import logging
from soil.models import SoilMoisture, SoilMoistureSourceChoices
from .provider import SoilMoistureProvider

logger = logging.getLogger(__name__)


class ReanalysisSoilMoistureProvider(SoilMoistureProvider):
    """
    Reanalysis soil moisture provider architecture.
    Designed for future ingestion pipelines (e.g., ECMWF ERA5-Land 0.1° resolution grids).

    Pipeline design:
        Farm coordinates (lat/lng)
              ↓
        Reanalysis Provider (e.g. ERA5-Land volumetric soil water layer 1-4)
              ↓
        Normalized SoilMoisture (PERCENT, layer depth e.g. 7cm, 28cm, 100cm)
              ↓
        Database persistence with source='REANALYSIS'
    """

    def __init__(self, dataset_name='era5_land'):
        self.dataset_name = dataset_name

    def get_current(self, farm, depth=None):
        """
        Query database for latest ingested reanalysis reading.
        Returns None if no reanalysis data has been ingested.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.REANALYSIS,
        )
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('-timestamp').first()

    def get_history(self, farm, start_date=None, end_date=None, depth=None):
        """
        Query historical reanalysis readings for the farm.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.REANALYSIS,
        )
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('timestamp')

    def fetch_from_remote(self, latitude, longitude, timestamp=None):
        """
        Prepared hook for future remote reanalysis data extraction.
        Stage 4 does not fake reanalysis data.
        """
        logger.info(
            f"Reanalysis provider remote fetch requested for ({latitude}, {longitude}). "
            "Remote reanalysis pipeline not activated in Stage 4."
        )
        return None
