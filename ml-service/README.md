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

## Database Structure

- `User` (Django native)
  - `FarmerProfile` (1:1 with User)
    - `Farm` (1:N with FarmerProfile)
      - `CropProfile` (1:N with Farm)
        - `GrowthStage` (Extensible model, N:1 with CropProfile)

## Setup Instructions

### 1. Environment Variables

Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Ensure you provide a valid `MAPBOX_ACCESS_TOKEN`. (For local development, `DATABASE_URL` is commented out by default to use SQLite).

### 2. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database Migration

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

### 5. Run Server

```bash
python manage.py runserver
```

### 6. Run Tests

```bash
python manage.py test
```

## Known Limitations (Stage 1)
- Currently uses SQLite for local development out-of-the-box (PostgreSQL configuration is ready via `DATABASE_URL` in `.env`).
- No weather data or machine learning models are implemented yet.
- Mapbox geocoding runs synchronously during farm creation.
- `GrowthStage` objects currently need to be seeded into the database manually or via the admin panel.

## Future Development Roadmap (Stage 2+)
- **Stage 2**: Weather APIs integration (IMD, ECMWF, GFS).
- **Stage 3**: Crop-risk and irrigation machine learning models.
- **Stage 4**: Proactive alerts and Celery/Redis integration.
- **Stage 5**: ClimaGPT LLM multilingual chatbot integration.
