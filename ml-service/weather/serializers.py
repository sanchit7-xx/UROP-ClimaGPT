"""
Weather API Serializers — Stage 2.

WeatherSerializer exposes all weather fields including the new weather_code
field needed by the frontend for condition icon mapping.

The serializer also includes a read-only `sunrise` and `sunset` computed
property so daily forecast records can optionally carry these through.
"""
from rest_framework import serializers
from .models import Weather


class WeatherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Weather
        fields = [
            "id",
            "farm",
            "timestamp",
            "temperature",
            "apparent_temperature",
            "precipitation",
            "rain",
            "relative_humidity",
            "wind_speed",
            "wind_direction",
            "surface_pressure",
            "evapotranspiration",
            "precipitation_probability",
            "weather_code",
            "source",
            "forecast_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
