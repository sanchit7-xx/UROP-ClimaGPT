"""
soil/services/sensor_provider.py

Sensor-specific SoilMoistureProvider implementation.
Handles physical / IoT farm sensor readings and queries.
"""
import logging
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from soil.models import SoilMoisture, SoilMoistureSourceChoices, SoilMoistureUnitChoices
from .provider import SoilMoistureProvider

logger = logging.getLogger(__name__)


class SensorSoilMoistureProvider(SoilMoistureProvider):
    """
    Provider backed by in-situ soil moisture sensors (IoT, telemetry, or farmer manual input).
    """

    def get_current(self, farm, depth=None):
        """
        Return the latest valid sensor reading for this farm.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.SENSOR,
        )
        if depth is not None:
            qs = qs.filter(depth=depth)
        return qs.order_by('-timestamp').first()

    def get_history(self, farm, start_date=None, end_date=None, depth=None):
        """
        Return sensor reading history for this farm ordered chronologically.
        """
        qs = SoilMoisture.objects.filter(
            farm=farm,
            source=SoilMoistureSourceChoices.SENSOR,
        )
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)
        if depth is not None:
            qs = qs.filter(depth=depth)

        return qs.order_by('timestamp')

    def ingest_reading(self, farm, validated_data):
        """
        Store a validated sensor reading for the farm.
        Returns the created SoilMoisture record.
        """
        timestamp = validated_data['timestamp']
        moisture = validated_data['moisture']
        unit = validated_data.get('unit', SoilMoistureUnitChoices.PERCENT)
        depth = validated_data.get('depth', 20)
        confidence = validated_data.get('confidence', 0.98 if validated_data.get('confidence') is None else validated_data.get('confidence'))

        # Check for duplicate
        existing = SoilMoisture.objects.filter(
            farm=farm,
            timestamp=timestamp,
            depth=depth,
            source=SoilMoistureSourceChoices.SENSOR,
        ).first()

        if existing:
            raise ValidationError(
                f"Duplicate reading: A sensor reading for farm '{farm.farm_name}' at depth {depth}cm "
                f"and timestamp {timestamp.isoformat()} already exists."
            )

        reading = SoilMoisture(
            farm=farm,
            latitude=farm.latitude,
            longitude=farm.longitude,
            timestamp=timestamp,
            moisture=moisture,
            unit=unit,
            depth=depth,
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=confidence,
        )
        reading.full_clean()
        reading.save()
        logger.info(
            f"Ingested sensor soil moisture reading for farm {farm.id}: "
            f"{moisture}% at {depth}cm ({timestamp})"
        )
        return reading
