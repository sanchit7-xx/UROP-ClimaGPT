"""
weather/pipeline/cleaner.py

HistoricalWeatherCleaner — Cleans records, detects duplicates, timestamp gaps, and statistical outliers.

Key Responsibilities:
  1. Duplicate Detection: deduplicates by (farm_id, timestamp, source, forecast_type).
  2. Missing Data Gap Detection: checks for expected hourly intervals without fabricating values.
  3. Outlier Detection: distinguishes PHYSICALLY INVALID (rejected in validator) vs STATISTICALLY UNUSUAL (extreme weather events preserved for Stage 6 research).
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class HistoricalWeatherCleaner:
    """Cleans valid weather records, deduplicates, flags gaps & statistical outliers."""

    # Statistical outlier thresholds (statistically unusual extreme events preserved for research)
    TEMP_UNUSUAL_HIGH = 45.0  # °C
    TEMP_UNUSUAL_LOW = -10.0  # °C
    PRECIP_UNUSUAL_HIGH = 100.0  # mm/hr
    WIND_UNUSUAL_HIGH = 90.0  # km/h

    def __init__(self, expected_interval_hours: float = 1.0):
        self.expected_interval = timedelta(hours=expected_interval_hours)

    def clean(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Clean and deduplicate records, inspect missing timestamp gaps, and flag outliers.

        Returns (cleaned_records, cleaning_stats_report).
        """
        if not records:
            return [], {
                'duplicates_removed': 0,
                'missing_gaps_detected': 0,
                'outliers_flagged': 0,
                'cleaned_count': 0,
            }

        # 1. Deduplication
        seen_keys = set()
        deduped_records = []
        duplicates_removed = 0

        for r in records:
            farm_id = r.get('farm_id')
            ts = r.get('timestamp')
            source = r.get('source', 'OPEN_METEO')
            forecast_type = r.get('forecast_type', 'HISTORICAL')
            key = (farm_id, ts, source, forecast_type)

            if key in seen_keys:
                duplicates_removed += 1
                logger.info(f"Cleaner: Duplicate record skipped for key {key}")
            else:
                seen_keys.add(key)
                deduped_records.append(dict(r))

        # Sort by timestamp for gap analysis
        def parse_ts(item):
            t = item.get('timestamp')
            if isinstance(t, datetime):
                return t
            try:
                return datetime.fromisoformat(str(t).replace('Z', '+00:00'))
            except Exception:
                return datetime.min

        deduped_records.sort(key=parse_ts)

        # 2. Missing Data Gap Detection
        missing_gaps_detected = 0
        gap_details = []

        for i in range(1, len(deduped_records)):
            prev_time = parse_ts(deduped_records[i - 1])
            curr_time = parse_ts(deduped_records[i])

            if prev_time != datetime.min and curr_time != datetime.min:
                diff = curr_time - prev_time
                if diff > self.expected_interval + timedelta(minutes=5):
                    missing_gaps_detected += 1
                    gap_details.append({
                        'from': prev_time.isoformat(),
                        'to': curr_time.isoformat(),
                        'gap_hours': round(diff.total_seconds() / 3600.0, 2),
                    })

        # 3. Outlier Detection (Statistically Unusual vs Physically Invalid)
        outliers_flagged = 0
        for r in deduped_records:
            outlier_flags = []
            temp = r.get('temperature')
            if temp is not None:
                if temp > self.TEMP_UNUSUAL_HIGH or temp < self.TEMP_UNUSUAL_LOW:
                    outlier_flags.append(f"Statistically unusual temperature: {temp}°C")

            precip = r.get('precipitation')
            if precip is not None and precip > self.PRECIP_UNUSUAL_HIGH:
                outlier_flags.append(f"Statistically unusual extreme precipitation: {precip} mm")

            wind = r.get('wind_speed')
            if wind is not None and wind > self.WIND_UNUSUAL_HIGH:
                outlier_flags.append(f"Statistically unusual extreme wind: {wind} km/h")

            if outlier_flags:
                outliers_flagged += 1
                r['is_statistically_unusual'] = True
                r['outlier_flags'] = outlier_flags
                logger.info(f"Cleaner: Flagged extreme event at {r.get('timestamp')}: {outlier_flags}")
            else:
                r['is_statistically_unusual'] = False
                r['outlier_flags'] = []

        cleaning_stats = {
            'duplicates_removed': duplicates_removed,
            'missing_gaps_detected': missing_gaps_detected,
            'gap_details': gap_details,
            'outliers_flagged': outliers_flagged,
            'cleaned_count': len(deduped_records),
        }

        logger.info(f"Cleaner complete: {len(deduped_records)} cleaned, {duplicates_removed} duplicates, {missing_gaps_detected} gaps, {outliers_flagged} outliers")
        return deduped_records, cleaning_stats
