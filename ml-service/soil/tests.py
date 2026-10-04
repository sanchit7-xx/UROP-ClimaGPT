"""
soil/tests.py

Comprehensive tests for ClimaGPT Stage 4:
- SoilMoisture Model & Validation
- Source Enum (SENSOR, SATELLITE, REANALYSIS, ESTIMATED)
- Moisture Unit & Depth Validation
- Soil Moisture Provider Architecture
- Sensor Ingestion API (POST /api/soil-moisture/sensor/)
- Current Soil Moisture API (GET /api/soil-moisture/farms/<farm_id>/current/)
- Historical Soil Moisture API (GET /api/soil-moisture/farms/<farm_id>/history/)
- Environmental State Service & API (GET /api/environment/farms/<farm_id>/state/)
- Farm Ownership & Authentication Security
- Duplicate Prevention & Missing Data Handling
- Strict Exclusion of Irrigation / Crop Risk Predictions
"""
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from accounts.models import FarmerProfile
from farms.models import Farm, AreaUnitChoices, IrrigationTypeChoices
from crops.models import CropProfile, SoilTypeChoices
from weather.models import Weather, ForecastTypeChoices
from soil.models import (
    SoilMoisture,
    SoilMoistureSourceChoices,
    SoilMoistureUnitChoices,
)
from soil.services import (
    SoilMoistureProviderFactory,
    SensorSoilMoistureProvider,
    SatelliteSoilMoistureProvider,
    ReanalysisSoilMoistureProvider,
    EstimatedSoilMoistureProvider,
    EnvironmentalStateService,
)

User = get_user_model()


class SoilMoistureBaseTestCase(APITestCase):
    """Base setup with authenticated farmers, farms, and test fixtures."""

    def setUp(self):
        # Farmer A (Primary)
        self.user_a = User.objects.create_user(
            username='farmer_a',
            email='farmer_a@climagpt.org',
            password='TestPassword123!',
        )
        self.profile_a = FarmerProfile.objects.create(
            user=self.user_a,
            full_name='Ramesh Kumar',
            phone_number='+919876543210',
            state='Maharashtra',
            district='Pune',
        )
        self.token_a = Token.objects.create(user=self.user_a)

        # Farmer B (Secondary — for unauthorized access tests)
        self.user_b = User.objects.create_user(
            username='farmer_b',
            email='farmer_b@climagpt.org',
            password='TestPassword123!',
        )
        self.profile_b = FarmerProfile.objects.create(
            user=self.user_b,
            full_name='Suresh Patel',
            phone_number='+919876543211',
            state='Gujarat',
            district='Surat',
        )
        self.token_b = Token.objects.create(user=self.user_b)

        # Farm belonging to Farmer A
        self.farm_a = Farm.objects.create(
            farmer=self.profile_a,
            farm_name='Green Acres Plot 1',
            farm_area=5.0,
            farm_area_unit=AreaUnitChoices.ACRE,
            irrigation_type=IrrigationTypeChoices.DRIP,
            latitude='18.520400',
            longitude='73.856700',
            village='Haveli',
            district='Pune',
            state='Maharashtra',
        )

        # Farm belonging to Farmer B
        self.farm_b = Farm.objects.create(
            farmer=self.profile_b,
            farm_name='Sunrise Valley',
            farm_area=3.5,
            farm_area_unit=AreaUnitChoices.ACRE,
            irrigation_type=IrrigationTypeChoices.BOREWELL,
            latitude='21.170200',
            longitude='72.831100',
            village='Olpad',
            district='Surat',
            state='Gujarat',
        )


class SoilMoistureModelTests(SoilMoistureBaseTestCase):
    """1. SoilMoisture model, sources, units, depth, confidence, and validation."""

    def test_create_valid_soil_moisture_record(self):
        reading = SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=timezone.now(),
            moisture=24.5,
            unit=SoilMoistureUnitChoices.PERCENT,
            depth=20,
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=0.98,
        )
        self.assertEqual(reading.moisture, 24.5)
        self.assertEqual(reading.unit, 'PERCENT')
        self.assertEqual(reading.depth, 20)
        self.assertEqual(reading.source, 'SENSOR')
        self.assertEqual(reading.confidence, 0.98)
        self.assertEqual(reading.confidence_level, 'High')
        # Check auto-filled lat/long from farm
        self.assertEqual(float(reading.latitude), float(self.farm_a.latitude))
        self.assertEqual(float(reading.longitude), float(self.farm_a.longitude))
        self.assertIn("24.5PERCENT", str(reading))

    def test_source_enum_values(self):
        self.assertEqual(SoilMoistureSourceChoices.SENSOR, 'SENSOR')
        self.assertEqual(SoilMoistureSourceChoices.SATELLITE, 'SATELLITE')
        self.assertEqual(SoilMoistureSourceChoices.REANALYSIS, 'REANALYSIS')
        self.assertEqual(SoilMoistureSourceChoices.ESTIMATED, 'ESTIMATED')

    def test_confidence_levels_mapping(self):
        sm_high = SoilMoisture(farm=self.farm_a, timestamp=timezone.now(), moisture=20.0, confidence=0.85)
        self.assertEqual(sm_high.confidence_level, 'High')

        sm_med = SoilMoisture(farm=self.farm_a, timestamp=timezone.now(), moisture=20.0, confidence=0.65)
        self.assertEqual(sm_med.confidence_level, 'Medium')

        sm_low = SoilMoisture(farm=self.farm_a, timestamp=timezone.now(), moisture=20.0, confidence=0.30)
        self.assertEqual(sm_low.confidence_level, 'Low')

        sm_none = SoilMoisture(farm=self.farm_a, timestamp=timezone.now(), moisture=20.0, confidence=None)
        self.assertEqual(sm_none.confidence_level, 'Not provided')

    def test_invalid_moisture_percentage_out_of_bounds(self):
        # Greater than 100%
        with self.assertRaises(ValidationError):
            reading = SoilMoisture(
                farm=self.farm_a,
                timestamp=timezone.now(),
                moisture=105.0,
                unit=SoilMoistureUnitChoices.PERCENT,
            )
            reading.clean()

        # Less than 0%
        with self.assertRaises(ValidationError):
            reading = SoilMoisture(
                farm=self.farm_a,
                timestamp=timezone.now(),
                moisture=-5.0,
                unit=SoilMoistureUnitChoices.PERCENT,
            )
            reading.clean()

    def test_invalid_confidence_out_of_bounds(self):
        with self.assertRaises(ValidationError):
            reading = SoilMoisture(
                farm=self.farm_a,
                timestamp=timezone.now(),
                moisture=25.0,
                confidence=1.5,
            )
            reading.clean()

    def test_duplicate_prevention_on_farm_timestamp_depth_source(self):
        now = timezone.now()
        SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=now,
            moisture=22.0,
            depth=20,
            source=SoilMoistureSourceChoices.SENSOR,
        )

        with self.assertRaises(Exception):
            # Duplicate at exact same farm, timestamp, depth, source
            SoilMoisture.objects.create(
                farm=self.farm_a,
                timestamp=now,
                moisture=24.0,
                depth=20,
                source=SoilMoistureSourceChoices.SENSOR,
            )

        # Different depth at same timestamp is allowed
        diff_depth = SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=now,
            moisture=28.0,
            depth=50,
            source=SoilMoistureSourceChoices.SENSOR,
        )
        self.assertEqual(diff_depth.depth, 50)


class SoilMoistureProviderArchitectureTests(SoilMoistureBaseTestCase):
    """Soil moisture provider interface & factory architecture tests."""

    def test_provider_factory_resolution(self):
        sensor_provider = SoilMoistureProviderFactory.get_provider(SoilMoistureSourceChoices.SENSOR)
        self.assertIsInstance(sensor_provider, SensorSoilMoistureProvider)

        sat_provider = SoilMoistureProviderFactory.get_provider(SoilMoistureSourceChoices.SATELLITE)
        self.assertIsInstance(sat_provider, SatelliteSoilMoistureProvider)

        reanalysis_provider = SoilMoistureProviderFactory.get_provider(SoilMoistureSourceChoices.REANALYSIS)
        self.assertIsInstance(reanalysis_provider, ReanalysisSoilMoistureProvider)

        estimated_provider = SoilMoistureProviderFactory.get_provider(SoilMoistureSourceChoices.ESTIMATED)
        self.assertIsInstance(estimated_provider, EstimatedSoilMoistureProvider)

    def test_sensor_provider_queries_and_ingestion(self):
        provider = SensorSoilMoistureProvider()
        now = timezone.now()

        # Ingestion
        reading = provider.ingest_reading(self.farm_a, {
            'timestamp': now,
            'moisture': 23.4,
            'unit': 'PERCENT',
            'depth': 20,
            'confidence': 0.95,
        })
        self.assertIsNotNone(reading.id)

        # Current
        current = provider.get_current(self.farm_a)
        self.assertEqual(current.id, reading.id)
        self.assertEqual(current.moisture, 23.4)

        # History
        history = list(provider.get_history(self.farm_a))
        self.assertEqual(len(history), 1)

    def test_satellite_and_reanalysis_providers_honest_no_fake_data(self):
        sat_provider = SatelliteSoilMoistureProvider()
        self.assertIsNone(sat_provider.get_current(self.farm_a))
        self.assertIsNone(sat_provider.fetch_from_remote(18.5204, 73.8567))

        reanalysis_provider = ReanalysisSoilMoistureProvider()
        self.assertIsNone(reanalysis_provider.get_current(self.farm_a))
        self.assertIsNone(reanalysis_provider.fetch_from_remote(18.5204, 73.8567))

        estimated_provider = EstimatedSoilMoistureProvider()
        self.assertIsNone(estimated_provider.get_current(self.farm_a))


class SensorIngestionAPITests(SoilMoistureBaseTestCase):
    """POST /api/soil-moisture/sensor/ — Sensor ingestion & validation."""

    url = '/api/soil-moisture/sensor/'

    def test_unauthenticated_request_rejected(self):
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 24.5,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': timezone.now().isoformat(),
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successful_sensor_ingestion(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 24.5,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': '2026-10-04T10:00:00Z',
            'confidence': 0.98,
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['moisture'], 24.5)
        self.assertEqual(res.data['unit'], 'PERCENT')
        self.assertEqual(res.data['depth'], 20)
        self.assertEqual(res.data['source'], 'SENSOR')
        self.assertEqual(res.data['confidence'], 0.98)
        self.assertEqual(res.data['confidence_level'], 'High')
        self.assertEqual(res.data['farm_id'], self.farm_a.id)

    def test_farm_ownership_validation_farmer_b_cannot_submit_to_farm_a(self):
        # Farmer B tries to submit reading to Farmer A's farm
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_b.key}')
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 24.5,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': '2026-10-04T10:00:00Z',
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('farm_id', res.data)

    def test_invalid_moisture_value_validation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        # Moisture > 100%
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 125.0,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': '2026-10-04T10:00:00Z',
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('moisture', res.data)

        # Moisture < 0%
        payload['moisture'] = -10.0
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_depth_validation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 25.0,
            'unit': 'PERCENT',
            'depth': -5,
            'timestamp': '2026-10-04T10:00:00Z',
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('depth', res.data)

    def test_invalid_timestamp_validation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 25.0,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': 'invalid-date-format',
        }
        res = self.client.post(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timestamp', res.data)

    def test_duplicate_sensor_reading_prevention(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        payload = {
            'farm_id': self.farm_a.id,
            'moisture': 24.5,
            'unit': 'PERCENT',
            'depth': 20,
            'timestamp': '2026-10-04T10:00:00Z',
        }
        res1 = self.client.post(self.url, payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Resubmit exact same reading
        res2 = self.client.post(self.url, payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', str(res2.data))


class CurrentSoilMoistureAPITests(SoilMoistureBaseTestCase):
    """GET /api/soil-moisture/farms/<farm_id>/current/ — Latest reading."""

    def test_unauthenticated_request_rejected(self):
        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/current/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_farmer_access_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_b.key}')
        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/current/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_data_returns_proper_unavailable_response(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/current/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(res.data['available'])
        self.assertIn("Soil moisture data is not available", res.data['detail'])
        self.assertIn("SENSOR", res.data['possible_sources'])

    def test_latest_reading_returned_successfully(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        now = timezone.now()

        # Insert older reading
        SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=now - timedelta(hours=2),
            moisture=20.0,
            depth=20,
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=0.95,
        )
        # Insert newer reading
        newer = SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=now,
            moisture=24.5,
            depth=20,
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=0.98,
        )

        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/current/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['available'])
        self.assertEqual(res.data['moisture'], 24.5)
        self.assertEqual(res.data['depth'], 20)
        self.assertEqual(res.data['confidence'], 0.98)
        self.assertEqual(res.data['source'], 'SENSOR')


class SoilMoistureHistoryAPITests(SoilMoistureBaseTestCase):
    """GET /api/soil-moisture/farms/<farm_id>/history/ — History & filters."""

    def setUp(self):
        super().setUp()
        self.base_time = timezone.now() - timedelta(days=5)
        for i in range(5):
            SoilMoisture.objects.create(
                farm=self.farm_a,
                timestamp=self.base_time + timedelta(days=i),
                moisture=20.0 + i,
                unit=SoilMoistureUnitChoices.PERCENT,
                depth=20,
                source=SoilMoistureSourceChoices.SENSOR,
                confidence=0.95,
            )

    def test_unauthenticated_request_rejected(self):
        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/history/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_history_list_retrieval(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        res = self.client.get(f'/api/soil-moisture/farms/{self.farm_a.id}/history/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['farm_id'], self.farm_a.id)
        self.assertEqual(res.data['count'], 5)
        self.assertEqual(len(res.data['results']), 5)

    def test_date_range_filtering(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        start = (self.base_time + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (self.base_time + timedelta(days=3)).strftime('%Y-%m-%d')

        res = self.client.get(
            f'/api/soil-moisture/farms/{self.farm_a.id}/history/?start_date={start}&end_date={end}'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 3)

    def test_invalid_date_format_handling(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        res = self.client.get(
            f'/api/soil-moisture/farms/{self.farm_a.id}/history/?start_date=2026/09/01'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid start_date format", res.data['detail'])


class EnvironmentalStateAPITests(SoilMoistureBaseTestCase):
    """GET /api/environment/farms/<farm_id>/state/ — Assembled state & constraints."""

    def test_unauthenticated_request_rejected(self):
        res = self.client.get(f'/api/environment/farms/{self.farm_a.id}/state/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_farmer_access_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_b.key}')
        res = self.client.get(f'/api/environment/farms/{self.farm_a.id}/state/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_assembled_environmental_state_with_all_components(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        now = timezone.now()

        # 1. Add soil moisture
        SoilMoisture.objects.create(
            farm=self.farm_a,
            timestamp=now,
            moisture=24.5,
            depth=20,
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=0.98,
        )

        # 2. Add weather record
        Weather.objects.create(
            farm=self.farm_a,
            timestamp=now,
            temperature=31.2,
            apparent_temperature=33.0,
            relative_humidity=72.0,
            precipitation=4.2,
            rain=4.2,
            wind_speed=12.5,
            evapotranspiration=0.3,
            weather_code=61,
            forecast_type=ForecastTypeChoices.CURRENT,
        )

        # 3. Add crop profile with soil type
        CropProfile.objects.create(
            farm=self.farm_a,
            crop_name='Wheat',
            crop_variety='HD 2967',
            sowing_date=date(2026, 10, 1),
            soil_type=SoilTypeChoices.LOAMY,
        )

        res = self.client.get(f'/api/environment/farms/{self.farm_a.id}/state/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data['farm_id'], self.farm_a.id)
        self.assertEqual(data['farm_name'], self.farm_a.farm_name)

        # Soil moisture check
        self.assertIsNotNone(data['soil_moisture'])
        self.assertEqual(data['soil_moisture']['value'], 24.5)
        self.assertEqual(data['soil_moisture']['depth'], 20)
        self.assertEqual(data['soil_moisture']['source'], 'SENSOR')
        self.assertEqual(data['soil_moisture']['confidence_level'], 'High')

        # Weather check
        self.assertIsNotNone(data['weather'])
        self.assertEqual(data['weather']['temperature'], 31.2)
        self.assertEqual(data['weather']['humidity'], 72.0)
        self.assertEqual(data['weather']['evapotranspiration'], 0.3)
        self.assertEqual(data['weather']['recent_precipitation'], 4.2)

        # Soil check
        self.assertEqual(data['soil']['type'], 'loamy')
        self.assertEqual(data['soil']['display_name'], 'Loamy')

        # STRICT EXCLUSION: Ensure NO future prediction fields exist
        forbidden_keys = [
            'irrigation_recommendation', 'recommendation', 'advice',
            'action', 'water_now', 'crop_risk', 'risk_score',
            'waterlogging_risk', 'flood_risk', 'decision',
        ]
        for key in forbidden_keys:
            self.assertNotIn(key, data, f"Stage 4 state must NOT contain future stage key '{key}'")

    def test_assembled_state_when_data_is_partially_missing(self):
        # Farm has no soil moisture, no crops, no weather records
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        res = self.client.get(f'/api/environment/farms/{self.farm_a.id}/state/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data['farm_id'], self.farm_a.id)
        self.assertIsNone(data['soil_moisture'])
        self.assertEqual(data['soil']['display_name'], 'Not specified')
