"""
soil/models.py

Stage 4: Soil Moisture & Farm Environmental State

Normalized SoilMoisture model storing moisture readings from sensors,
satellites, reanalysis models, or estimates.
"""
from django.core.exceptions import ValidationError
from django.db import models

from farms.models import Farm


class SoilMoistureSourceChoices(models.TextChoices):
    """
    Source of soil moisture data.
    Stage 4 implements SENSOR and prepares SATELLITE, REANALYSIS, ESTIMATED.
    """
    SENSOR = 'SENSOR', 'Sensor'
    SATELLITE = 'SATELLITE', 'Satellite'
    REANALYSIS = 'REANALYSIS', 'Reanalysis'
    ESTIMATED = 'ESTIMATED', 'Estimated'


class SoilMoistureUnitChoices(models.TextChoices):
    """
    Measurement units for soil moisture.
    Initial standard: PERCENT (0-100%).
    Extensible for volumetric (m³/m³) in future stages.
    """
    PERCENT = 'PERCENT', 'Percent'


class SoilMoisture(models.Model):
    """
    Normalized soil moisture record for a specific farm, depth, and timestamp.

    Traceability:
        farm, location (lat/lon), timestamp, moisture, unit, depth, source, confidence.

    Duplicate prevention:
        unique_together = ('farm', 'timestamp', 'depth', 'source') prevents duplicate
        ingestions while allowing readings at different depths or timestamps.
    """
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='soil_moisture_records',
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitude where reading was taken (defaults to farm latitude).',
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitude where reading was taken (defaults to farm longitude).',
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text='UTC timestamp of measurement.',
    )
    moisture = models.FloatField(
        help_text='Soil moisture reading as a numerical value.',
    )
    unit = models.CharField(
        max_length=20,
        choices=SoilMoistureUnitChoices.choices,
        default=SoilMoistureUnitChoices.PERCENT,
        help_text='Unit of moisture measurement.',
    )
    depth = models.PositiveIntegerField(
        default=20,
        help_text='Depth in centimeters (e.g. 5, 20, 50 cm). Non-negative integer.',
    )
    source = models.CharField(
        max_length=20,
        choices=SoilMoistureSourceChoices.choices,
        default=SoilMoistureSourceChoices.SENSOR,
        help_text='Data source provider type.',
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text='Confidence score between 0.0 and 1.0 (null if uncalibrated/unavailable).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Soil Moisture Record'
        verbose_name_plural = 'Soil Moisture Records'
        ordering = ['-timestamp']
        unique_together = ('farm', 'timestamp', 'depth', 'source')
        indexes = [
            models.Index(fields=['farm', '-timestamp']),
            models.Index(fields=['farm', 'depth', '-timestamp']),
            models.Index(fields=['farm', 'source', '-timestamp']),
        ]

    def __str__(self):
        return (
            f"SoilMoisture farm={self.farm_id} "
            f"{self.moisture}{self.unit} @ {self.depth}cm "
            f"[{self.source}] ({self.timestamp})"
        )

    def clean(self):
        super().clean()
        from decimal import Decimal, ROUND_HALF_UP

        if self.latitude is not None:
            try:
                self.latitude = Decimal(str(self.latitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            except Exception:
                pass
        if self.longitude is not None:
            try:
                self.longitude = Decimal(str(self.longitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            except Exception:
                pass

        if self.moisture is None:
            raise ValidationError({'moisture': 'Moisture value cannot be null.'})

        # Unit-specific range validation
        if self.unit == SoilMoistureUnitChoices.PERCENT:
            if not (0.0 <= float(self.moisture) <= 100.0):
                raise ValidationError({
                    'moisture': f'Moisture percentage must be between 0.0 and 100.0, got {self.moisture}.'
                })

        # Depth validation
        if self.depth is not None and self.depth < 0:
            raise ValidationError({'depth': 'Depth must be non-negative (>= 0 cm).'})

        # Confidence validation
        if self.confidence is not None:
            if not (0.0 <= float(self.confidence) <= 1.0):
                raise ValidationError({
                    'confidence': f'Confidence must be between 0.0 and 1.0, got {self.confidence}.'
                })

    def save(self, *args, **kwargs):
        from decimal import Decimal, ROUND_HALF_UP
        # Auto-fill lat/lon from farm if not explicitly provided
        if self.farm:
            if self.latitude is None and self.farm.latitude is not None:
                self.latitude = Decimal(str(self.farm.latitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            if self.longitude is None and self.farm.longitude is not None:
                self.longitude = Decimal(str(self.farm.longitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        if self.latitude is not None:
            try:
                self.latitude = Decimal(str(self.latitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            except Exception:
                pass
        if self.longitude is not None:
            try:
                self.longitude = Decimal(str(self.longitude)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            except Exception:
                pass

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def confidence_level(self):
        """
        Farmer-friendly qualitative confidence representation.
        Returns: 'High', 'Medium', 'Low', or 'Not provided'.
        """
        if self.confidence is None:
            return 'Not provided'
        if self.confidence >= 0.80:
            return 'High'
        if self.confidence >= 0.50:
            return 'Medium'
        return 'Low'
