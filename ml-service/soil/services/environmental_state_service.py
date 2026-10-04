"""
soil/services/environmental_state_service.py

Stage 4: Assembles current environmental state for a farm.
Aggregates:
- Latest soil moisture
- Current weather (temperature, humidity, recent rainfall, ET)
- Soil type from crop profile

STRICT CONSTRAINT:
Only describes the current physical environmental state.
Does NOT make irrigation recommendations, crop risk predictions, or waterlogging predictions.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum

from farms.models import Farm
from crops.models import CropProfile
from weather.models import Weather, ForecastTypeChoices
from weather.services.weather_service import WeatherService
from soil.models import SoilMoisture

logger = logging.getLogger(__name__)


class EnvironmentalStateService:
    """
    Assembles real-time environmental context for a specific farm.
    """

    @classmethod
    def get_farm_environmental_state(cls, farm: Farm) -> dict:
        """
        Gathers available soil, weather, and physical characteristics.
        Missing or unavailable values are set to None without fabrication.
        """
        now = timezone.now()

        # ── 1. Soil Moisture ──────────────────────────────────────────
        latest_sm = SoilMoisture.objects.filter(farm=farm).order_by('-timestamp').first()
        soil_moisture_data = None
        if latest_sm:
            soil_moisture_data = {
                "value": latest_sm.moisture,
                "unit": latest_sm.unit,
                "depth": latest_sm.depth,
                "source": latest_sm.source,
                "confidence": latest_sm.confidence,
                "confidence_level": latest_sm.confidence_level,
                "timestamp": latest_sm.timestamp.isoformat(),
            }

        # ── 2. Weather & Recent Rainfall ──────────────────────────────
        current_weather_obj = Weather.objects.filter(
            farm=farm,
            forecast_type=ForecastTypeChoices.CURRENT,
        ).order_by('-timestamp').first()

        # If no current weather cached in DB, attempt a lookup via WeatherService
        if not current_weather_obj:
            try:
                weather_results = WeatherService.get_weather(farm, ForecastTypeChoices.CURRENT)
                if weather_results:
                    current_weather_obj = weather_results[0]
            except Exception as e:
                logger.warning(f"Could not retrieve live weather for farm {farm.id}: {e}")

        # Compute recent precipitation (past 24 hours)
        past_24h = now - timedelta(hours=24)
        precip_sum = Weather.objects.filter(
            farm=farm,
            timestamp__gte=past_24h,
            timestamp__lte=now,
        ).aggregate(total_precip=Sum('precipitation'))['total_precip']

        if precip_sum is None:
            # Fall back to current record's precipitation if available
            recent_precip = current_weather_obj.precipitation if current_weather_obj else None
        else:
            recent_precip = round(float(precip_sum), 2)

        weather_data = None
        if current_weather_obj:
            weather_data = {
                "temperature": current_weather_obj.temperature,
                "apparent_temperature": current_weather_obj.apparent_temperature,
                "humidity": current_weather_obj.relative_humidity,
                "wind_speed": current_weather_obj.wind_speed,
                "recent_precipitation": recent_precip,
                "evapotranspiration": current_weather_obj.evapotranspiration,
                "weather_code": current_weather_obj.weather_code,
                "timestamp": current_weather_obj.timestamp.isoformat(),
            }

        # ── 3. Soil Type ──────────────────────────────────────────────
        latest_crop_with_soil = CropProfile.objects.filter(
            farm=farm
        ).exclude(soil_type='').order_by('-created_at').first()

        soil_type_val = None
        soil_type_display = "Not specified"
        if latest_crop_with_soil and latest_crop_with_soil.soil_type:
            soil_type_val = latest_crop_with_soil.soil_type
            soil_type_display = latest_crop_with_soil.get_soil_type_display()

        soil_data = {
            "type": soil_type_val,
            "display_name": soil_type_display,
        }

        return {
            "farm_id": farm.id,
            "farm_name": farm.farm_name,
            "timestamp": now.isoformat(),
            "soil_moisture": soil_moisture_data,
            "weather": weather_data,
            "soil": soil_data,
        }
