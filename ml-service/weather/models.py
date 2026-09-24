from django.db import models

from farms.models import Farm

class WeatherSourceChoices(models.TextChoices):
    OPEN_METEO = 'OPEN_METEO', 'Open-Meteo'
    # Future sources: IMD, ECMWF, GFS, NASA, etc.

class ForecastTypeChoices(models.TextChoices):
    CURRENT = 'CURRENT', 'Current Weather'
    HOURLY = 'HOURLY_FORECAST', 'Hourly Forecast'
    DAILY = 'DAILY_FORECAST', 'Daily Forecast'
    HISTORICAL = 'HISTORICAL', 'Historical'  # Stage 3 will implement historical pipeline

class Weather(models.Model):
    """
    Normalized weather record for a specific farm, timestamp, and forecast type.

    weather_code stores the WMO (World Meteorological Organization) code returned
    by Open-Meteo. The frontend maps these codes to human-readable descriptions
    and emoji icons (e.g., 0 → ☀️ Clear Sky, 61 → 🌧️ Slight Rain).

    Indexes and unique_together prevent duplicate records while supporting
    legitimate forecast updates across different timestamps.
    """
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='weather_records')
    timestamp = models.DateTimeField()
    temperature = models.FloatField(null=True, blank=True)
    apparent_temperature = models.FloatField(null=True, blank=True)
    precipitation = models.FloatField(null=True, blank=True)
    rain = models.FloatField(null=True, blank=True)
    relative_humidity = models.FloatField(null=True, blank=True)
    wind_speed = models.FloatField(null=True, blank=True)
    wind_direction = models.FloatField(null=True, blank=True)
    surface_pressure = models.FloatField(null=True, blank=True)
    evapotranspiration = models.FloatField(null=True, blank=True)
    precipitation_probability = models.FloatField(null=True, blank=True)
    # WMO weather interpretation code — used by frontend to display condition icons
    weather_code = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=WeatherSourceChoices.choices, default=WeatherSourceChoices.OPEN_METEO)
    forecast_type = models.CharField(max_length=20, choices=ForecastTypeChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'timestamp', 'forecast_type', 'source')
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['farm', 'forecast_type', 'timestamp']),
        ]

    def __str__(self):
        return f"Weather {self.farm.farm_name} {self.timestamp} {self.forecast_type}"
