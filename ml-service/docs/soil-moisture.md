# ClimaGPT — Stage 4: Soil Moisture & Farm Environmental State

## 1. Overview & Objectives

Stage 4 establishes the foundation for soil moisture monitoring and farm environmental state analysis within ClimaGPT. It introduces:
- A normalized database model (`SoilMoisture`) with research traceability (farm, coordinates, timestamp, depth, source, confidence, unit).
- In-situ sensor telemetry ingestion API (`POST /api/soil-moisture/sensor/`).
- Historical soil moisture API (`GET /api/soil-moisture/farms/<farm_id>/history/`).
- Current soil moisture API (`GET /api/soil-moisture/farms/<farm_id>/current/`).
- Farm Environmental State Service (`EnvironmentalStateService`) and API (`GET /api/environment/farms/<farm_id>/state/`).
- Dynamic frontend dashboard visualization with dark-mode glassmorphism aesthetics, line chart, data table, and demo sensor ingestion modal.

> **CRITICAL BOUNDARY:** Stage 4 is strictly an environmental-state diagnostic foundation. It **does NOT** provide irrigation recommendations, crop risk predictions, or waterlogging risk assessments. Those capabilities belong to subsequent stages (Stage 8, 9, 10, and 11).

---

## 2. Soil Moisture Model & Architecture

### Model Schema (`soil.models.SoilMoisture`)

| Field | Type | Description |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `farm` | `ForeignKey(farms.Farm)` | Related farm plot |
| `latitude` | `DecimalField(9, 6)` | Coordinate latitude (auto-filled from farm if omitted) |
| `longitude` | `DecimalField(9, 6)` | Coordinate longitude (auto-filled from farm if omitted) |
| `timestamp` | `DateTimeField` | UTC measurement timestamp |
| `moisture` | `FloatField` | Moisture reading value |
| `unit` | `CharField` | Unit enum (default: `PERCENT`, 0.0–100.0%) |
| `depth` | `PositiveIntegerField` | Measurement depth in centimeters (e.g. 5, 20, 50 cm) |
| `source` | `CharField` | Provider source (`SENSOR`, `SATELLITE`, `REANALYSIS`, `ESTIMATED`) |
| `confidence` | `FloatField` (nullable) | Statistical calibration confidence score (0.0 to 1.0) |
| `created_at` | `DateTimeField` | Ingestion timestamp |
| `updated_at` | `DateTimeField` | Record update timestamp |

### Indexes & Duplicate Prevention
- `unique_together = ('farm', 'timestamp', 'depth', 'source')`: Prevents accidental duplicate sensor submissions at identical depth and time, while allowing multi-depth profiling (e.g., 5 cm, 20 cm, 50 cm simultaneously).
- DB Indexes on `('farm', '-timestamp')`, `('farm', 'depth', '-timestamp')`, and `('farm', 'source', '-timestamp')` optimize range and history queries.

---

## 3. Data Sources & Confidence

### Source Types (`SoilMoistureSourceChoices`)
1. **`SENSOR`**: Physical in-situ hardware telemetry installed on the farmer's plot.
2. **`SATELLITE`**: Remote sensing products (e.g., NASA SMAP, ESA Sentinel-1 radar). Architecture prepared.
3. **`REANALYSIS`**: Land surface reanalysis models (e.g., ECMWF ERA5-Land). Architecture prepared.
4. **`ESTIMATED`**: Water-balance approximations. Must never fabricate values or simulate data without explicit user intent.

### Confidence Representation
Confidence is represented honestly:
- **High**: $\ge 0.80$ (typical for calibrated physical sensors)
- **Medium**: $0.50 \le \text{confidence} < 0.80$
- **Low**: $< 0.50$
- **Not provided**: Stored as `null` if uncalibrated, never invented.

---

## 4. API Endpoints

### 1. Ingest Sensor Reading
`POST /api/soil-moisture/sensor/`

**Headers:**
- `Authorization: Token <token>`
- `Content-Type: application/json`

**Request Body:**
```json
{
    "farm_id": 1,
    "moisture": 24.5,
    "unit": "PERCENT",
    "depth": 20,
    "timestamp": "2026-10-04T10:00:00Z",
    "confidence": 0.98
}
```

**Response (201 Created):**
```json
{
    "id": 1,
    "farm_id": 1,
    "latitude": "18.520400",
    "longitude": "73.856700",
    "timestamp": "2026-10-04T10:00:00Z",
    "moisture": 24.5,
    "unit": "PERCENT",
    "depth": 20,
    "source": "SENSOR",
    "confidence": 0.98,
    "confidence_level": "High",
    "created_at": "2026-10-04T10:00:02Z"
}
```

### 2. Query Current Soil Moisture
`GET /api/soil-moisture/farms/{farm_id}/current/`

**Response (200 OK — Data Available):**
```json
{
    "id": 1,
    "farm_id": 1,
    "latitude": "18.520400",
    "longitude": "73.856700",
    "timestamp": "2026-10-04T10:00:00Z",
    "moisture": 24.5,
    "unit": "PERCENT",
    "depth": 20,
    "source": "SENSOR",
    "confidence": 0.98,
    "confidence_level": "High",
    "available": true,
    "created_at": "2026-10-04T10:00:02Z"
}
```

**Response (404 Not Found — No Sensor Connected):**
```json
{
    "farm_id": 1,
    "available": false,
    "detail": "Soil moisture data is not available for this farm.",
    "possible_sources": ["SENSOR", "SATELLITE", "REANALYSIS"]
}
```

### 3. Query Soil Moisture History
`GET /api/soil-moisture/farms/{farm_id}/history/?start_date=2026-09-01&end_date=2026-10-04&depth=20`

**Response (200 OK):**
```json
{
    "farm_id": 1,
    "count": 5,
    "results": [
        {
            "id": 1,
            "farm_id": 1,
            "timestamp": "2026-10-01T08:00:00Z",
            "moisture": 21.0,
            "unit": "PERCENT",
            "depth": 20,
            "source": "SENSOR",
            "confidence": 0.95,
            "confidence_level": "High"
        }
    ]
}
```

### 4. Farm Environmental State
`GET /api/environment/farms/{farm_id}/state/`

Consolidates all current physical parameters without predictions:
```json
{
    "farm_id": 1,
    "farm_name": "Green Acres Plot 1",
    "timestamp": "2026-10-04T11:00:00Z",
    "soil_moisture": {
        "value": 24.5,
        "unit": "PERCENT",
        "depth": 20,
        "source": "SENSOR",
        "confidence": 0.98,
        "confidence_level": "High",
        "timestamp": "2026-10-04T10:00:00Z"
    },
    "weather": {
        "temperature": 31.2,
        "apparent_temperature": 33.0,
        "humidity": 72.0,
        "wind_speed": 12.5,
        "recent_precipitation": 4.2,
        "evapotranspiration": 0.3,
        "weather_code": 61,
        "timestamp": "2026-10-04T10:30:00Z"
    },
    "soil": {
        "type": "loamy",
        "display_name": "Loamy"
    }
}
```

---

## 5. Frontend Dashboard

The farmer dashboard displays:
1. **Soil & Environment Section**:
   - Current Soil Moisture card with moisture percentage, depth in cm, source badge (`🟢 Sensor`, `🔵 Satellite`, `🟣 Reanalysis`, `🟡 Estimated`), confidence badge, and timestamp.
   - Farm Environmental State card reporting temperature, relative humidity, recent rainfall, evapotranspiration, and soil type.
2. **Honest Data Handling**:
   - If no sensor data is present, the UI clearly displays "Soil moisture data is not available for this farm" and explains future sources. No dummy values are used.
3. **Soil Moisture History Chart**:
   - High-DPI Canvas-based responsive line chart showing moisture fluctuations over time with glowing gradient fills.
4. **Data Quality & History Table**:
   - Displays record counts, latest updates, and collapsible tabular data.
5. **Sensor Ingestion (Demo / Hardware)**:
   - Accessible via "Ingest Sensor Data" modal with quick preset button.

---

## 6. Provider Extensibility & Limitations

### Provider Architecture
```
Farm coordinates (lat/lng)
          ↓
SoilMoistureProviderFactory
          ↓
Source-specific implementation:
  - SensorSoilMoistureProvider (Active)
  - SatelliteSoilMoistureProvider (Prepared)
  - ReanalysisSoilMoistureProvider (Prepared)
  - EstimatedSoilMoistureProvider (Prepared)
          ↓
Normalized SoilMoisture DB Record
```

### Limitations & Future Integrations
- Physical sensor telemetry requires hardware connected via HTTP API.
- Satellite radar passes (e.g. SMAP) have coarse spatial resolution (9–36 km) and typically measure topsoil (0–5 cm depth), which will be addressed in future fusion stages.
