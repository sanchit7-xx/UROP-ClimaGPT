"""
soil/services/satellite_provider.py

Prepared architecture for Satellite Soil Moisture Products (e.g., SMAP, Sentinel-1, Copernicus).
Stage 4 prepares the service interface without faking external network endpoints.
"""
import logging
from soil.models import SoilMoisture, SoilMoistureSourceChoices
from .provider import SoilMoistureProvider

logger = logging.getLogger(__name__)


class SatelliteSoilMoistureProvider(SoilMoistureProvider):
    """
    Satellite soil moisture provider architecture.
    Designed for future ingestion pipelines (e.g. NASA SMAP, ESA CCI, Copernicus).

    Pipeline design:
        Farm coordinates (lat/lng)
              ↓
        Satellite Provider (e.g. SMAP / Sentinel-1 raster query)
              ↓
        Normalized SoilMoisture (PERCENT, depth 0-5cm)
              ↓
        Database persistence with source='SATELLITE'
    """

    def __init__(self, api_key=None, product_name='SMAP_L3_SM_P'):
        self.api_key = api_key
        self.product_name = product_name

    def get_current(self, farm, depth=None):
        """
        Query database for latest ingested satellite reading.
        Returns None if no satellite data has been ingested.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.SATELLITE,
        )
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('-timestamp').first()

    def get_history(self, farm, start_date=None, end_date=None, depth=None):
        """
        Query historical satellite readings for the farm.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.SATELLITE,
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
        Prepared hook for future remote satellite API fetching.
        Stage 4 explicitly reports this as not yet activated rather than inventing fake data.
        """
        logger.info(
            f"Satellite provider remote fetch requested for ({latitude}, {longitude}). "
            "Remote satellite API not activated in Stage 4."
        )
        return None
