"""
weather/services/historical_weather_service.py

HistoricalWeatherService — High-level orchestration service for historical weather pipeline.

Pipeline Steps:
  1. HistoricalWeatherCollector → fetches raw historical weather from provider.
  2. HistoricalWeatherValidator → validates numeric physical bounds.
  3. HistoricalWeatherCleaner → deduplicates, inspects missing timestamp gaps, flags extreme outliers.
  4. HistoricalWeatherNormalizer → standardizes units and ISO UTC timestamps.
  5. DB Persistence → stores cleaned historical records into Weather model with forecast_type='HISTORICAL'.
  6. HistoricalDatasetBuilder → builds reproducible tabular dataset for CSV / Parquet export.

All summary metrics and data quality indicators are derived from real historical data.
"""
import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Tuple

from django.core.cache import cache
from django.conf import settings
from django.db.models import Avg, Max, Min, Sum

from farms.models import Farm
from weather.models import Weather, ForecastTypeChoices, WeatherSourceChoices
from weather.pipeline.collector import HistoricalWeatherCollector
from weather.pipeline.validator import HistoricalWeatherValidator
from weather.pipeline.cleaner import HistoricalWeatherCleaner
from weather.pipeline.normalizer import HistoricalWeatherNormalizer
from weather.pipeline.dataset_builder import HistoricalDatasetBuilder

logger = logging.getLogger(__name__)


class HistoricalWeatherService:
    """Orchestrates data pipeline, database persistence, summaries, and export."""

    @staticmethod
    def _cache_key(farm_id: int, start_date: str, end_date: str) -> str:
        return f"historical_weather:{farm_id}:{start_date}:{end_date}"

    @classmethod
    def collect_and_process(
        cls,
        farm: Farm,
        start_date: str,
        end_date: str,
    ) -> Tuple[List[Weather], Dict[str, Any]]:
        """
        Execute full historical data processing pipeline and save cleaned records to DB.

        Returns (stored_weather_objects, data_quality_report).
        """
        collector = HistoricalWeatherCollector()
        validator = HistoricalWeatherValidator()
        cleaner = HistoricalWeatherCleaner()
        normalizer = HistoricalWeatherNormalizer()

        # Step 1: Collect
        raw_records = collector.collect(farm, start_date, end_date)

        # Step 2: Validate
        valid_records, invalid_records = validator.validate(raw_records)

        # Step 3: Clean
        cleaned_records, cleaning_stats = cleaner.clean(valid_records)

        # Step 4: Normalize
        normalized_records = normalizer.normalize(cleaned_records)

        # Step 5: DB Storage
        stored_objs = []
        for entry in normalized_records:
            obj, _ = Weather.objects.update_or_create(
                farm=farm,
                timestamp=entry['timestamp'],
                forecast_type=ForecastTypeChoices.HISTORICAL,
                source=WeatherSourceChoices.OPEN_METEO,
                defaults={
                    'temperature': entry.get('temperature'),
                    'apparent_temperature': entry.get('apparent_temperature'),
                    'precipitation': entry.get('precipitation'),
                    'rain': entry.get('rain'),
                    'relative_humidity': entry.get('relative_humidity'),
                    'wind_speed': entry.get('wind_speed'),
                    'wind_direction': entry.get('wind_direction'),
                    'surface_pressure': entry.get('surface_pressure'),
                    'evapotranspiration': entry.get('evapotranspiration'),
                    'precipitation_probability': entry.get('precipitation_probability'),
                    'weather_code': entry.get('weather_code'),
                },
            )
            stored_objs.append(obj)

        # Build Quality Report
        total_count = len(raw_records)
        invalid_count = len(invalid_records)
        missing_gaps = cleaning_stats.get('missing_gaps_detected', 0)
        duplicates_removed = cleaning_stats.get('duplicates_removed', 0)
        outliers_count = cleaning_stats.get('outliers_flagged', 0)

        quality_status = "Good" if (invalid_count == 0 and missing_gaps == 0) else "Review required"

        quality_report = {
            'total_records': total_count,
            'valid_records': len(valid_records),
            'missing_values_count': missing_gaps,
            'duplicates_count': duplicates_removed,
            'invalid_records_count': invalid_count,
            'outliers_count': outliers_count,
            'quality_status': quality_status,
            'last_collected': datetime.now(timezone.utc).isoformat(),
            'source': WeatherSourceChoices.OPEN_METEO,
        }

        # Cache results for 30 minutes
        cache_key = cls._cache_key(farm.id, start_date, end_date)
        cache_timeout = getattr(settings, 'WEATHER_CACHE_MINUTES', 30) * 60
        cache.set(cache_key, (stored_objs, quality_report), timeout=cache_timeout)

        logger.info(f"HistoricalWeatherService: Successfully processed and saved {len(stored_objs)} records for farm {farm.id}")
        return stored_objs, quality_report

    @classmethod
    def get_historical_weather(
        cls,
        farm: Farm,
        start_date: str,
        end_date: str,
        force_collect: bool = False,
    ) -> List[Weather]:
        """
        Get historical weather records for a farm between start_date and end_date (YYYY-MM-DD).

        If records do not exist in DB or force_collect=True, triggers data collection pipeline.
        """
        if not force_collect:
            # Query existing records from DB
            qs = Weather.objects.filter(
                farm=farm,
                forecast_type=ForecastTypeChoices.HISTORICAL,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date,
            ).order_by('timestamp')

            if qs.exists():
                logger.info(f"HistoricalWeatherService: Returning {qs.count()} cached DB records for farm {farm.id}")
                return list(qs)

        # Trigger collection pipeline if missing in DB
        records, _ = cls.collect_and_process(farm, start_date, end_date)
        return records

    @classmethod
    def get_historical_summary(
        cls,
        farm: Farm,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Calculate summary metrics over historical weather data for a farm and date range.

        Returns real calculated metrics:
          - average / minimum / maximum temperature
          - total precipitation
          - average humidity
          - average wind speed
          - record count
          - quality report & data source
        """
        records = cls.get_historical_weather(farm, start_date, end_date)

        if not records:
            return {
                'farm_id': farm.id,
                'start_date': start_date,
                'end_date': end_date,
                'record_count': 0,
                'avg_temperature': None,
                'min_temperature': None,
                'max_temperature': None,
                'total_precipitation': 0.0,
                'avg_humidity': None,
                'avg_wind_speed': None,
                'source': WeatherSourceChoices.OPEN_METEO,
                'last_collected': None,
                'quality_report': {
                    'total_records': 0,
                    'valid_records': 0,
                    'missing_values_count': 0,
                    'duplicates_count': 0,
                    'invalid_records_count': 0,
                    'outliers_count': 0,
                    'quality_status': 'No data',
                    'last_collected': None,
                    'source': WeatherSourceChoices.OPEN_METEO,
                }
            }

        # Calculate aggregations over queryset
        qs = Weather.objects.filter(
            farm=farm,
            forecast_type=ForecastTypeChoices.HISTORICAL,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date,
        )

        aggs = qs.aggregate(
            avg_temp=Avg('temperature'),
            min_temp=Min('temperature'),
            max_temp=Max('temperature'),
            total_precip=Sum('precipitation'),
            avg_hum=Avg('relative_humidity'),
            avg_wind=Avg('wind_speed'),
        )

        last_record = qs.order_by('-updated_at').first()
        last_collected = last_record.updated_at.isoformat() if last_record else datetime.now(timezone.utc).isoformat()

        cache_key = cls._cache_key(farm.id, start_date, end_date)
        cached_tuple = cache.get(cache_key)
        if cached_tuple and isinstance(cached_tuple, tuple) and len(cached_tuple) == 2:
            quality_report = cached_tuple[1]
        else:
            quality_report = {
                'total_records': len(records),
                'valid_records': len(records),
                'missing_values_count': 0,
                'duplicates_count': 0,
                'invalid_records_count': 0,
                'outliers_count': sum(1 for r in records if getattr(r, 'temperature', 0) and (r.temperature > 45 or r.temperature < -10)),
                'quality_status': 'Good',
                'last_collected': last_collected,
                'source': WeatherSourceChoices.OPEN_METEO,
            }

        return {
            'farm_id': farm.id,
            'start_date': start_date,
            'end_date': end_date,
            'record_count': len(records),
            'avg_temperature': round(aggs['avg_temp'], 1) if aggs['avg_temp'] is not None else None,
            'min_temperature': round(aggs['min_temp'], 1) if aggs['min_temp'] is not None else None,
            'max_temperature': round(aggs['max_temp'], 1) if aggs['max_temp'] is not None else None,
            'total_precipitation': round(aggs['total_precip'] or 0.0, 1),
            'avg_humidity': round(aggs['avg_hum'], 1) if aggs['avg_hum'] is not None else None,
            'avg_wind_speed': round(aggs['avg_wind'], 1) if aggs['avg_wind'] is not None else None,
            'source': WeatherSourceChoices.OPEN_METEO,
            'last_collected': last_collected,
            'quality_report': quality_report,
        }

    @classmethod
    def export_dataset(
        cls,
        farm: Farm,
        start_date: str,
        end_date: str,
        format_type: str = 'csv',
    ) -> Any:
        """Export cleaned historical dataset for farm as CSV string or Parquet bytes."""
        records = cls.get_historical_weather(farm, start_date, end_date)
        builder = HistoricalDatasetBuilder()

        if format_type.lower() == 'parquet':
            return builder.to_parquet(records)
        else:
            return builder.to_csv(records)
