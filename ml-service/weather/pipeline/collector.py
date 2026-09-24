"""
weather/pipeline/collector.py

HistoricalWeatherCollector — Retrieves raw historical weather records from provider.

Preserves:
  - source
  - farm & coordinates
  - timestamp
  - original raw weather values

Does NOT alter raw values before validation.
"""
import logging
from typing import List, Dict, Any

from farms.models import Farm
from weather.services import WeatherProviderFactory

logger = logging.getLogger(__name__)


class HistoricalWeatherCollector:
    """Retrieves raw historical weather data for a farm and date range."""

    def __init__(self, provider=None):
        self.provider = provider or WeatherProviderFactory.get_provider()

    def collect(self, farm: Farm, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch raw historical weather records for a farm from start_date to end_date (YYYY-MM-DD).

        Returns list of dicts with original raw weather parameters.
        """
        lat = float(farm.latitude)
        lon = float(farm.longitude)

        logger.info(f"Collector: Fetching raw historical weather for farm {farm.id} ({start_date} to {end_date})")

        raw_records = self.provider.fetch_historical(lat, lon, start_date, end_date)

        # Attach farm metadata to each raw record without mutating values
        for record in raw_records:
            record['farm_id'] = farm.id
            record['latitude'] = lat
            record['longitude'] = lon

        logger.info(f"Collector: Retrieved {len(raw_records)} raw historical records for farm {farm.id}")
        return raw_records
