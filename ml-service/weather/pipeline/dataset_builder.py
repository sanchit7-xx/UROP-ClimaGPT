"""
weather/pipeline/dataset_builder.py

HistoricalDatasetBuilder — Converts processed historical weather records into ML-ready tabular formats.

Outputs reproducible datasets containing:
  - timestamp
  - farm_id
  - latitude
  - longitude
  - temperature (°C)
  - apparent_temperature (°C)
  - precipitation (mm)
  - rain (mm)
  - relative_humidity (%)
  - wind_speed (km/h)
  - wind_direction (deg)
  - surface_pressure (hPa)
  - evapotranspiration (mm)
  - weather_code
  - source

Supports export to CSV and Parquet formats.
Does NOT create prediction targets or lag features (those belong to Stage 5).
"""
import csv
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

CSV_HEADERS = [
    'timestamp',
    'farm_id',
    'latitude',
    'longitude',
    'temperature',
    'apparent_temperature',
    'precipitation',
    'rain',
    'relative_humidity',
    'wind_speed',
    'wind_direction',
    'surface_pressure',
    'evapotranspiration',
    'weather_code',
    'source',
]


class HistoricalDatasetBuilder:
    """Converts cleaned historical weather objects or dicts into tabular formats."""

    @staticmethod
    def _extract_dict(item: Any) -> Dict[str, Any]:
        """Convert Weather model instance or dict to standardized dict."""
        if hasattr(item, 'farm'):
            return {
                'timestamp': item.timestamp.isoformat() if hasattr(item.timestamp, 'isoformat') else str(item.timestamp),
                'farm_id': item.farm_id,
                'latitude': float(item.farm.latitude) if item.farm else None,
                'longitude': float(item.farm.longitude) if item.farm else None,
                'temperature': item.temperature,
                'apparent_temperature': item.apparent_temperature,
                'precipitation': item.precipitation,
                'rain': item.rain,
                'relative_humidity': item.relative_humidity,
                'wind_speed': item.wind_speed,
                'wind_direction': item.wind_direction,
                'surface_pressure': item.surface_pressure,
                'evapotranspiration': item.evapotranspiration,
                'weather_code': item.weather_code,
                'source': item.source,
            }
        elif isinstance(item, dict):
            ts = item.get('timestamp')
            ts_str = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
            return {
                'timestamp': ts_str,
                'farm_id': item.get('farm_id'),
                'latitude': item.get('latitude'),
                'longitude': item.get('longitude'),
                'temperature': item.get('temperature'),
                'apparent_temperature': item.get('apparent_temperature'),
                'precipitation': item.get('precipitation'),
                'rain': item.get('rain'),
                'relative_humidity': item.get('relative_humidity'),
                'wind_speed': item.get('wind_speed'),
                'wind_direction': item.get('wind_direction'),
                'surface_pressure': item.get('surface_pressure'),
                'evapotranspiration': item.get('evapotranspiration'),
                'weather_code': item.get('weather_code'),
                'source': item.get('source', 'OPEN_METEO'),
            }
        return {}

    def build_tabular(self, records: List[Any]) -> List[Dict[str, Any]]:
        """Build tabular list of rows matching dataset schema."""
        return [self._extract_dict(r) for r in records]

    def to_csv(self, records: List[Any]) -> str:
        """Export records as a CSV string."""
        tabular_data = self.build_tabular(records)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in tabular_data:
            writer.writerow(row)
        return output.getvalue()

    def to_parquet(self, records: List[Any]) -> bytes:
        """
        Export records as Parquet bytes.
        Requires pandas/pyarrow or fastparquet. Raises NotImplementedError with guidance if missing.
        """
        try:
            import pandas as pd
            tabular_data = self.build_tabular(records)
            df = pd.DataFrame(tabular_data)
            buf = io.BytesIO()
            df.to_parquet(buf, index=False)
            return buf.getvalue()
        except ImportError as err:
            logger.warning(f"Parquet export requested but dependencies missing: {err}")
            raise NotImplementedError(
                "Parquet export requires pandas and pyarrow/fastparquet. "
                "Please install them via `pip install pandas pyarrow` to enable Parquet export."
            )
