"""
weather/pipeline/normalizer.py

HistoricalWeatherNormalizer — Normalizes historical weather records into standard internal units and ISO UTC timestamps.

Units:
  - Temperature: °C
  - Apparent Temperature: °C
  - Precipitation / Rain: mm
  - Wind speed: km/h
  - Pressure: hPa
  - Humidity: %
  - Evapotranspiration: mm

Timestamps:
  - ISO 8601 UTC datetimes
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class HistoricalWeatherNormalizer:
    """Normalizes raw/cleaned weather dictionary values into standardized internal representation."""

    @staticmethod
    def parse_timestamp(ts_val: Any) -> datetime:
        """Parse timestamp value into UTC timezone-aware datetime."""
        if ts_val is None:
            return datetime.now(timezone.utc)
        if isinstance(ts_val, datetime):
            if ts_val.tzinfo is None:
                return ts_val.replace(tzinfo=timezone.utc)
            return ts_val
        try:
            dt = datetime.fromisoformat(str(ts_val).replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            logger.warning(f"Normalizer: Failed to parse timestamp '{ts_val}', using UTC now.")
            return datetime.now(timezone.utc)

    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize units and timestamp for a single weather record dict."""
        normalized = dict(record)

        # Standardize timestamp
        ts = self.parse_timestamp(record.get('timestamp'))
        normalized['timestamp'] = ts

        # Float fields rounded safely
        float_fields = [
            'temperature', 'apparent_temperature', 'precipitation', 'rain',
            'relative_humidity', 'wind_speed', 'wind_direction',
            'surface_pressure', 'evapotranspiration', 'precipitation_probability'
        ]

        for field in float_fields:
            val = record.get(field)
            if val is not None:
                try:
                    normalized[field] = round(float(val), 2)
                except (ValueError, TypeError):
                    normalized[field] = None
            else:
                normalized[field] = None

        if record.get('weather_code') is not None:
            try:
                normalized['weather_code'] = int(record['weather_code'])
            except (ValueError, TypeError):
                normalized['weather_code'] = None

        return normalized

    def normalize(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize a list of weather record dicts."""
        normalized_list = [self.normalize_record(r) for r in records]
        logger.info(f"Normalizer: Standardized {len(normalized_list)} records to UTC and standard units.")
        return normalized_list
