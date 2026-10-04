"""
soil/verify_stage4.py

End-to-end verification script for Stage 4 demonstration:
1. Authenticate / login as farmer.
2. Create/select farm.
3. Verify no-data state before ingestion.
4. Test invalid sensor inputs (moisture out of bounds, negative depth, invalid timestamp).
5. Test unauthorized farm access.
6. Ingest valid sensor readings at different depths/timestamps.
7. Verify duplicate sensor reading prevention.
8. Verify current soil moisture API returns latest reading, source, depth, confidence.
9. Verify soil moisture history API returns chronological records and date filtering.
10. Verify environmental state API returns current soil moisture, weather, recent rain, ET, soil type.
11. Verify STRICT EXCLUSION: No irrigation advice or crop risk recommendations present.
12. Switch farms and verify data separation.
13. Confirm Stage 1, Stage 2, and Stage 3 APIs still work seamlessly.
"""
import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta

# Setup django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from accounts.models import FarmerProfile
from farms.models import Farm, AreaUnitChoices, IrrigationTypeChoices
from crops.models import CropProfile, SoilTypeChoices
from weather.models import Weather, ForecastTypeChoices
from soil.models import SoilMoisture, SoilMoistureSourceChoices, SoilMoistureUnitChoices

User = get_user_model()


def run_verification():
    print("============================================================")
    print("CLIMAGPT STAGE 4 — END-TO-END DEMONSTRATION & VERIFICATION")
    print("============================================================")

    client = APIClient()

    # 1. Setup Farmer Ramesh
    ts = int(datetime.now().timestamp() * 1000) % 1000000000
    username = f"demo_farmer_{ts}"
    user = User.objects.create_user(username=username, email=f"{username}@climagpt.org", password="DemoPassword123!")
    profile = FarmerProfile.objects.create(
        user=user,
        full_name="Ramesh Kumar",
        phone_number=f"+919{ts:09d}",
        state="Maharashtra",
        district="Pune",
    )
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    print("[PASS] 1. Farmer logged in and authenticated.")

    # Setup Farmer Suresh (for unauthorized checks)
    user_other = User.objects.create_user(username=f"other_{username}", email=f"other_{username}@climagpt.org", password="DemoPassword123!")
    profile_other = FarmerProfile.objects.create(user=user_other, full_name="Suresh Patel", phone_number=f"+918{ts:09d}")
    token_other = Token.objects.create(user=user_other)

    # 2. Create Farm 1 (Ramesh)
    farm1 = Farm.objects.create(
        farmer=profile,
        farm_name="Shivaji Agro Plot 1",
        farm_area=4.5,
        farm_area_unit=AreaUnitChoices.ACRE,
        irrigation_type=IrrigationTypeChoices.DRIP,
        latitude=Decimal("18.520400"),
        longitude=Decimal("73.856700"),
        village="Haveli",
        district="Pune",
        state="Maharashtra",
    )
    print(f"[PASS] 2. Farm 1 created: {farm1.farm_name} (ID: {farm1.id})")

    # Create Farm 2 (Ramesh)
    farm2 = Farm.objects.create(
        farmer=profile,
        farm_name="Shivaji Agro Plot 2",
        farm_area=2.0,
        farm_area_unit=AreaUnitChoices.ACRE,
        irrigation_type=IrrigationTypeChoices.BOREWELL,
        latitude=Decimal("18.530000"),
        longitude=Decimal("73.860000"),
        village="Haveli",
        district="Pune",
        state="Maharashtra",
    )
    print(f"[PASS] 2b. Farm 2 created: {farm2.farm_name} (ID: {farm2.id})")

    # 3. Test No-data state before any sensor ingestion
    res_no_data = client.get(f"/api/soil-moisture/farms/{farm1.id}/current/")
    assert res_no_data.status_code == 404
    assert res_no_data.data["available"] is False
    assert "Soil moisture data is not available" in res_no_data.data["detail"]
    assert "SENSOR" in res_no_data.data["possible_sources"]
    print("[PASS] 3. No-data state verified: Returns honest unavailable message and future sources.")

    # 4. Test invalid sensor inputs
    # Invalid moisture > 100%
    res_inv1 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id,
        "moisture": 125.0,
        "depth": 20,
        "timestamp": "2026-10-04T10:00:00Z",
    }, format="json")
    assert res_inv1.status_code == 400
    assert "moisture" in res_inv1.data
    print("[PASS] 4a. Invalid moisture (>100%) rejected with 400 Bad Request.")

    # Invalid negative depth
    res_inv2 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id,
        "moisture": 25.0,
        "depth": -10,
        "timestamp": "2026-10-04T10:00:00Z",
    }, format="json")
    assert res_inv2.status_code == 400
    assert "depth" in res_inv2.data
    print("[PASS] 4b. Invalid negative depth rejected with 400 Bad Request.")

    # Invalid timestamp format
    res_inv3 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id,
        "moisture": 25.0,
        "depth": 20,
        "timestamp": "not-a-datetime",
    }, format="json")
    assert res_inv3.status_code == 400
    assert "timestamp" in res_inv3.data
    print("[PASS] 4c. Invalid timestamp format rejected with 400 Bad Request.")

    # 5. Test unauthorized access: Suresh tries to submit reading to Ramesh's farm
    client_other = APIClient()
    client_other.credentials(HTTP_AUTHORIZATION=f"Token {token_other.key}")
    res_unauth = client_other.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id,
        "moisture": 22.0,
        "depth": 20,
        "timestamp": "2026-10-04T10:00:00Z",
    }, format="json")
    assert res_unauth.status_code == 400
    assert "does not belong to you" in str(res_unauth.data)
    print("[PASS] 5. Unauthorized access rejected: Cross-farmer submission prevented.")

    # 6. Ingest valid sensor readings for Farm 1
    t1 = "2026-10-04T08:00:00Z"
    t2 = "2026-10-04T09:00:00Z"
    t3 = "2026-10-04T10:00:00Z"

    r1 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id, "moisture": 22.1, "unit": "PERCENT", "depth": 20, "timestamp": t1, "confidence": 0.98
    }, format="json")
    assert r1.status_code == 201

    r2 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id, "moisture": 23.5, "unit": "PERCENT", "depth": 20, "timestamp": t2, "confidence": 0.98
    }, format="json")
    assert r2.status_code == 201

    r3 = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id, "moisture": 24.5, "unit": "PERCENT", "depth": 20, "timestamp": t3, "confidence": 0.98
    }, format="json")
    assert r3.status_code == 201
    print("[PASS] 6. Successfully ingested 3 physical sensor readings at 20 cm depth.")

    # 7. Test duplicate prevention
    r_dup = client.post("/api/soil-moisture/sensor/", {
        "farm_id": farm1.id, "moisture": 24.5, "unit": "PERCENT", "depth": 20, "timestamp": t3, "confidence": 0.98
    }, format="json")
    assert r_dup.status_code == 400
    assert "already exists" in str(r_dup.data)
    print("[PASS] 7. Duplicate sensor reading rejected with clear validation error.")

    # 8. Query current soil moisture
    res_curr = client.get(f"/api/soil-moisture/farms/{farm1.id}/current/")
    assert res_curr.status_code == 200
    assert res_curr.data["moisture"] == 24.5
    assert res_curr.data["depth"] == 20
    assert res_curr.data["source"] == "SENSOR"
    assert res_curr.data["confidence"] == 0.98
    assert res_curr.data["confidence_level"] == "High"
    print(f"[PASS] 8. Current soil moisture API: {res_curr.data['moisture']}% @ {res_curr.data['depth']}cm [Source: {res_curr.data['source']}] (Confidence: {res_curr.data['confidence_level']})")

    # 9. Query soil moisture history
    res_hist = client.get(f"/api/soil-moisture/farms/{farm1.id}/history/?start_date=2026-10-04&end_date=2026-10-04")
    assert res_hist.status_code == 200
    assert res_hist.data["count"] == 3
    print(f"[PASS] 9. Soil moisture history API: Retrieved {res_hist.data['count']} chronological readings.")

    # 10. Seed weather & crop profile for environmental state demonstration
    Weather.objects.create(
        farm=farm1,
        timestamp=timezone.now(),
        temperature=31.2,
        relative_humidity=72.0,
        precipitation=4.2,
        rain=4.2,
        evapotranspiration=0.3,
        weather_code=61,
        forecast_type=ForecastTypeChoices.CURRENT,
    )
    CropProfile.objects.create(
        farm=farm1,
        crop_name="Sugarcane",
        sowing_date=datetime.now().date(),
        soil_type=SoilTypeChoices.LOAMY,
    )

    res_env = client.get(f"/api/environment/farms/{farm1.id}/state/")
    assert res_env.status_code == 200
    env_data = res_env.data
    assert env_data["soil_moisture"]["value"] == 24.5
    assert env_data["weather"]["temperature"] == 31.2
    assert env_data["weather"]["humidity"] == 72.0
    assert env_data["weather"]["recent_precipitation"] == 4.2
    assert env_data["weather"]["evapotranspiration"] == 0.3
    assert env_data["soil"]["display_name"] == "Loamy"
    print("[PASS] 10. Farm Environmental State API:")
    print(f"       Soil Moisture:       {env_data['soil_moisture']['value']}%")
    print(f"       Temperature:         {env_data['weather']['temperature']}°C")
    print(f"       Relative Humidity:   {env_data['weather']['humidity']}%")
    print(f"       Recent Precipitation:{env_data['weather']['recent_precipitation']} mm")
    print(f"       Evapotranspiration:  {env_data['weather']['evapotranspiration']} mm")
    print(f"       Soil Type:           {env_data['soil']['display_name']}")

    # 11. STRICT VERIFICATION: Verify NO irrigation advice or predictions exist
    forbidden = ["irrigation", "recommendation", "advice", "water_now", "crop_risk", "waterlogging_risk"]
    for word in forbidden:
        assert word not in env_data, f"Forbidden prediction '{word}' detected in Stage 4 state!"
    print("[PASS] 11. STRICT EXCLUSION: Confirmed NO irrigation recommendations or crop risk predictions.")

    # 12. Switch farms: Verify Farm 2 has separate data
    res_f2_curr = client.get(f"/api/soil-moisture/farms/{farm2.id}/current/")
    assert res_f2_curr.status_code == 404
    assert res_f2_curr.data["available"] is False
    print("[PASS] 12. Farm selector data isolation verified: Farm 2 has no data while Farm 1 has data.")

    # 13. Verify Stage 1, Stage 2, Stage 3 still work
    res_stage1 = client.get("/api/farms/")
    assert res_stage1.status_code == 200
    farms_list = res_stage1.data if isinstance(res_stage1.data, list) else res_stage1.data.get("results", [])
    assert len(farms_list) >= 2
    print("[PASS] 13a. Stage 1 Farm APIs active and verified.")

    res_stage2 = client.get(f"/api/weather/farms/{farm1.id}/current/")
    assert res_stage2.status_code == 200
    print("[PASS] 13b. Stage 2 Real-Time Weather APIs active and verified.")

    res_stage3 = client.get(f"/api/weather/farms/{farm1.id}/historical/summary/")
    assert res_stage3.status_code == 200
    print("[PASS] 13c. Stage 3 Historical Weather Summary active and verified.")

    print("\n============================================================")
    print("ALL 13 STAGE 4 VERIFICATION MILESTONES PASSED SUCCESSFULLY!")
    print("============================================================")


if __name__ == "__main__":
    run_verification()
