"""
soil/services/estimated_provider.py

Prepared architecture for Estimated Soil Moisture.
Supports reading legitimately stored estimates while strictly forbidding fabrication of fake values.
"""
import logging
from soil.models import SoilMoisture, SoilMoistureSourceChoices
from .provider import SoilMoistureProvider

logger = logging.getLogger(__name__)


class EstimatedSoilMoistureProvider(SoilMoistureProvider):
    """
    Soil moisture provider for model-estimated or water-balance derived values.
    CRITICAL CONSTRAINT: Must NOT fabricate values or present estimated data as measured sensor data.
    """

    def get_current(self, farm, depth=None):
        """
        Return latest valid estimated reading from the database, or None.
        Does not fabricate random or unverified values.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.ESTIMATED,
        )
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('-timestamp').first()

    def get_history(self, farm, start_date=None, end_date=None, depth=None):
        """
        Query historical estimated readings for the farm.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.ESTIMATED,
        )
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('timestamp')
