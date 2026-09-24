"""
weather/pipeline/validator.py

HistoricalWeatherValidator — Validates raw historical weather records against physical constraints.

Validation Rules:
  - Temperature: numeric, -50.0 to +60.0 °C
  - Humidity: numeric, 0.0 to 100.0 %
  - Latitude: -90.0 to +90.0
  - Longitude: -180.0 to +180.0
  - Precipitation / Rain: numeric, >= 0.0 mm
  - Wind speed: numeric, >= 0.0 km/h
  - Surface pressure: numeric, 800.0 to 1100.0 hPa
  - Timestamp: valid parseable ISO string or datetime

Invalid records are flagged and recorded separately without silent replacement.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class HistoricalWeatherValidator:
    """Validates raw historical weather records."""

    TEMP_MIN, TEMP_MAX = -50.0, 60.0
    HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0
    PRESSURE_MIN, PRESSURE_MAX = 800.0, 1100.0
    LAT_MIN, LAT_MAX = -90.0, 90.0
    LON_MIN, LON_MAX = -180.0, 180.0

    @classmethod
    def validate_record(cls, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a single weather record. Returns (is_valid, list_of_error_reasons)."""
        errors = []

        # Timestamp check
        ts = record.get('timestamp')
        if not ts:
            errors.append("Missing timestamp")
        else:
            try:
                if isinstance(ts, str):
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                errors.append(f"Invalid timestamp format: {ts}")

        # Latitude / Longitude
        lat = record.get('latitude')
        if lat is not None:
            try:
                lat_val = float(lat)
                if not (cls.LAT_MIN <= lat_val <= cls.LAT_MAX):
                    errors.append(f"Latitude out of bounds: {lat_val}")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric latitude: {lat}")

        lon = record.get('longitude')
        if lon is not None:
            try:
                lon_val = float(lon)
                if not (cls.LON_MIN <= lon_val <= cls.LON_MAX):
                    errors.append(f"Longitude out of bounds: {lon_val}")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric longitude: {lon}")

        # Temperature
        temp = record.get('temperature')
        if temp is not None:
            try:
                temp_val = float(temp)
                if not (cls.TEMP_MIN <= temp_val <= cls.TEMP_MAX):
                    errors.append(f"Temperature out of physical bounds: {temp_val}°C")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric temperature: {temp}")

        # Relative Humidity
        hum = record.get('relative_humidity')
        if hum is not None:
            try:
                hum_val = float(hum)
                if not (cls.HUMIDITY_MIN <= hum_val <= cls.HUMIDITY_MAX):
                    errors.append(f"Humidity out of bounds: {hum_val}%")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric humidity: {hum}")

        # Precipitation
        precip = record.get('precipitation')
        if precip is not None:
            try:
                precip_val = float(precip)
                if precip_val < 0.0:
                    errors.append(f"Negative precipitation: {precip_val} mm")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric precipitation: {precip}")

        # Rain
        rain = record.get('rain')
        if rain is not None:
            try:
                rain_val = float(rain)
                if rain_val < 0.0:
                    errors.append(f"Negative rain: {rain_val} mm")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric rain: {rain}")

        # Wind Speed
        wind = record.get('wind_speed')
        if wind is not None:
            try:
                wind_val = float(wind)
                if wind_val < 0.0:
                    errors.append(f"Negative wind speed: {wind_val} km/h")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric wind speed: {wind}")

        # Surface Pressure
        press = record.get('surface_pressure')
        if press is not None:
            try:
                press_val = float(press)
                if not (cls.PRESSURE_MIN <= press_val <= cls.PRESSURE_MAX):
                    errors.append(f"Pressure out of reasonable range: {press_val} hPa")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric pressure: {press}")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate a list of records.

        Returns (valid_records, invalid_records_with_errors).
        """
        valid_records = []
        invalid_records = []

        for record in records:
            is_valid, errors = self.validate_record(record)
            if is_valid:
                valid_records.append(record)
            else:
                invalid_entry = dict(record)
                invalid_entry['validation_errors'] = errors
                invalid_records.append(invalid_entry)
                logger.warning(f"Validator: Rejected invalid record at {record.get('timestamp')}: {errors}")

        logger.info(f"Validator: {len(valid_records)} valid, {len(invalid_records)} invalid out of {len(records)} records")
        return valid_records, invalid_records
