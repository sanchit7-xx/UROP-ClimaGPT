"""
farms/models.py

Farm — one farmer can own multiple farms.

Location design:
  - latitude / longitude are the PRIMARY (canonical) farm location.
    They come from the farmer placing a marker on the map (Mapbox frontend).
  - All other address fields (village, city, district, …) are SUPPLEMENTARY.
    They are populated by reverse geocoding lat/lng via MapboxService and
    are stored for display convenience only.
  - Do NOT rely on city/district alone to identify a farm location.

Future stages will use latitude/longitude to query:
  - Weather grids (Open-Meteo, IMD, ECMWF)
  - NASA IMERG precipitation data
  - Soil moisture rasters
"""
from django.db import models

from core.models import TimeStampedModel


class IrrigationTypeChoices(models.TextChoices):
    """
    Extensible irrigation type choices.
    Add new entries here as the system grows; migrations will handle the rest.
    """
    RAIN_FED = 'rain_fed', 'Rain-fed'
    BOREWELL = 'borewell', 'Borewell'
    CANAL = 'canal', 'Canal'
    DRIP = 'drip', 'Drip'
    SPRINKLER = 'sprinkler', 'Sprinkler'
    OTHER = 'other', 'Other'


class AreaUnitChoices(models.TextChoices):
    """
    Extensible area unit choices to accommodate regional farming conventions.
    """
    HECTARE = 'ha', 'Hectare'
    ACRE = 'acre', 'Acre'
    SQUARE_METER = 'sqm', 'Square Meter'
    GUNTHA = 'guntha', 'Guntha'
    BIGHA = 'bigha', 'Bigha'
    OTHER = 'other', 'Other'


class Farm(TimeStampedModel):
    """
    A single farm belonging to a FarmerProfile.

    Relationships:
        Farm *──1 FarmerProfile   (one farmer owns many farms)
        Farm 1──* CropProfile     (via crops.CropProfile.farm FK)

    Stage 2 will add:
        Farm 1──* WeatherRecord
        Farm 1──* IrrigationAdvice
    """
    farmer = models.ForeignKey(
        'accounts.FarmerProfile',
        on_delete=models.CASCADE,
        related_name='farms',
    )
    farm_name = models.CharField(max_length=255)
    farm_area = models.DecimalField(max_digits=10, decimal_places=4)
    farm_area_unit = models.CharField(
        max_length=10,
        choices=AreaUnitChoices.choices,
        default=AreaUnitChoices.ACRE,
    )
    irrigation_type = models.CharField(
        max_length=20,
        choices=IrrigationTypeChoices.choices,
        default=IrrigationTypeChoices.RAIN_FED,
    )

    # ── Primary location (canonical — required) ───────────────────────────
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # ── Supplementary address (from Mapbox reverse geocoding — optional) ──
    village = models.CharField(max_length=150, blank=True)
    locality = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=150, blank=True)
    district = models.CharField(max_length=150, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Farm'
        verbose_name_plural = 'Farms'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.farm_name} — {self.farmer.full_name}'
