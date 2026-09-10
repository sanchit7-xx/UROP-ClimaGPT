# ClimaGPT API Documentation

Base URL: `http://localhost:8000/api/`

All endpoints (except `/health/`, `/auth/register/`, `/auth/login/`) require the `Authorization` header:
`Authorization: Token <your_token_here>`

---

## 1. Core Services

### `GET /api/health/`
- **Auth**: None
- **Response**: `200 OK`
- **Body**:
  ```json
  {
      "service": "ClimaGPT Django Service",
      "status": "healthy"
  }
  ```

---

## 2. Authentication & Account

### `POST /api/auth/register/`
- **Auth**: None
- **Body**:
  ```json
  {
      "full_name": "Farmer Name",
      "email": "farmer@example.com",
      "phone_number": "+919876543210",
      "password": "StrongPassword123!",
      "confirm_password": "StrongPassword123!",
      "preferred_language": "English",
      "state": "Maharashtra",
      "district": "Pune",
      "village": "Hadapsar"
  }
  ```
- **Response**: `201 Created` (returns `token` and `farmer` profile)

### `POST /api/auth/login/`
- **Auth**: None
- **Body**:
  ```json
  {
      "email": "farmer@example.com",
      "password": "StrongPassword123!"
  }
  ```
- **Response**: `200 OK` (returns `token` and `farmer` profile)

### `GET /api/farmer/profile/`
- **Auth**: Required
- **Response**: `200 OK` (returns authenticated user's profile)

### `PUT /api/farmer/profile/`
- **Auth**: Required
- **Body**: Partial updates allowed (e.g., `{"preferred_language": "Hindi"}`)
- **Response**: `200 OK`

---

## 3. Farms

### `GET /api/farms/`
- **Auth**: Required
- **Response**: `200 OK` (list of farms owned by the user)

### `POST /api/farms/`
- **Auth**: Required
- **Body**:
  ```json
  {
      "farm_name": "Wheat Field",
      "farm_area": "5.5",
      "farm_area_unit": "acre",
      "irrigation_type": "borewell",
      "latitude": "18.5204",
      "longitude": "73.8567"
  }
  ```
- **Response**: `201 Created` (if MAPBOX_ACCESS_TOKEN is set, returns auto-populated address fields)

### `GET /api/farms/<id>/`
- **Auth**: Required
- **Response**: `200 OK`

### `PUT /api/farms/<id>/`
- **Auth**: Required
- **Response**: `200 OK`

### `DELETE /api/farms/<id>/`
- **Auth**: Required
- **Response**: `204 No Content`

---

## 4. Crops

### `GET /api/farms/<farm_id>/crops/`
- **Auth**: Required
- **Response**: `200 OK` (list of crops on this farm)

### `POST /api/farms/<farm_id>/crops/`
- **Auth**: Required
- **Body**:
  ```json
  {
      "crop_name": "Wheat",
      "sowing_date": "2024-01-01",
      "expected_harvest_date": "2024-05-01",
      "growth_stage": 1,
      "soil_type": "loamy",
      "cultivation_method": "conventional"
  }
  ```
- **Response**: `201 Created`

### `GET /api/crops/<id>/`
- **Auth**: Required
- **Response**: `200 OK`

### `PUT /api/crops/<id>/`
- **Auth**: Required
- **Response**: `200 OK`

### `DELETE /api/crops/<id>/`
- **Auth**: Required
- **Response**: `204 No Content`

### `GET /api/crops/growth-stages/`
- **Auth**: Required
- **Query Params**: `?crop_type=wheat` (optional)
- **Response**: `200 OK` (returns list of available growth stages)

---

## 5. Dashboard

### `GET /api/dashboard/`
- **Auth**: Required
- **Response**: `200 OK`
  Returns an aggregated JSON payload containing:
  - `farmer`: Profile details
  - `summary`: Farm and crop counts
  - `farms`: Array of farms, each containing its respective `crops` list.
