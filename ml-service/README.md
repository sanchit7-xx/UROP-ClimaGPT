# ClimaGPT — Stage 1

**AI-Powered Weather, Crop Risk Prediction, Irrigation Decision Support and Early Warning System for Farmers**

This repository contains **Stage 1** of the project: the foundation for a RESTful Django backend handling complete farmer onboarding, multiple farms per farmer, crop lifecycle tracking, and Mapbox location integration.

## Technology Stack

- **Python**: 3.11+
- **Framework**: Django 4.2+ & Django REST Framework
- **Database**: PostgreSQL (via `psycopg2-binary`)
- **Authentication**: DRF Token Authentication
- **Environment**: `django-environ`

## Django Architecture

The project is highly modular to support future machine learning and API integrations:
- **`config/`**: Main Django configuration, URLs, WSGI/ASGI.
- **`core/`**: Abstract base models (`TimeStampedModel`), centralized exceptions, and the `MapboxService`.
- **`accounts/`**: Farmer profile and authentication APIs.
- **`farms/`**: Farm management APIs, ensuring location is rigorously tracked via GPS coordinates.
- **`crops/`**: Crop profiles, dynamic growth stages, and history.
- **`weather/`**: Real-time forecast, Open-Meteo provider, historical weather pipeline, and cleaned dataset exports (Stages 2 & 3).
- **`soil/`**: Soil moisture monitoring, sensor ingestion, and environmental state analysis (Stage 4).
- **`predictions/`**: Machine learning weather forecasting engine, feature engineering lag datasets, scikit-learn models, persistence baseline comparisons, and evaluation endpoints (Stage 5).

## Database Structure

- `User` (Django native)
  - `FarmerProfile` (1:1 with User)
    - `Farm` (1:N with FarmerProfile)
      - `CropProfile` (1:N with Farm)
        - `GrowthStage` (Extensible model, N:1 with CropProfile)
      - `Weather` (1:N with Farm, Stages 2 & 3)
      - `SoilMoisture` (1:N with Farm, Stage 4)
      - `ModelMetadata` (1:N with Farm / Global, Stage 5)
      - `PredictionLog` (Audit trail of ML predictions, Stage 5)

## Setup & Quickstart Guide for Team Members

### 1. Environment Setup
```bash
# Clone the repository and navigate to backend directory
cd ml-service

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables
Copy `.env.example` to `.env`:
```bash
# On Windows:
copy .env.example .env
# On Linux/macOS:
cp .env.example .env
```
*(By default SQLite is enabled for quick local development; configure `DATABASE_URL` if connecting to PostgreSQL).*

### 3. Database Migrations
```bash
python manage.py migrate
```

### 4. Machine Learning Models (Stage 5)
Pre-trained model artifacts are included in `predictions/ml/artifacts/`.
To re-train or train custom models for specific farms or globally:
```bash
# Train global baseline models:
python manage.py train_weather_models

# Train models specific to a farm:
python manage.py train_weather_models --farm-id 1
```

### 5. Running the Backend Server
```bash
python manage.py runserver 127.0.0.1:8000
```

### 6. Running the Frontend Dashboard
In a separate terminal, serve the `frontend/` folder:
```bash
# From repository root:
python -m http.server 3000 --directory frontend
```
Then visit **`http://localhost:3000`** in your browser.

### 7. Running Automated Tests
```bash
python manage.py test
```
All 124 tests across `accounts`, `farms`, `weather`, `soil`, and `predictions` will execute.

## Documentation References
- Stage 4: [docs/soil-moisture.md](docs/soil-moisture.md) — Soil Moisture & Environmental State Architecture.
- Stage 5: [predictions/](predictions/) — ML Weather Prediction Models, Lags Feature Engineering, and Inference Engine.

## Completed Stages
- **Stage 1**: Farmer Onboarding, Farm Registry, Location Tracking & Crop Lifecycles.
- **Stage 2**: Real-time Current Weather, Hourly Forecast (24h) & 7-Day Forecast.
- **Stage 3**: Historical Weather Ingestion, Validation/Cleaning/Normalizing Pipeline, and Quality Summaries.
- **Stage 4**: Multi-depth Soil Moisture Monitoring, Sensor Ingestion & Environmental State Analysis.
- **Stage 5**: AI Weather Prediction Engine (RandomForest/GradientBoosting), 24-hr Forecast Horizons, and Baseline Evaluation.

