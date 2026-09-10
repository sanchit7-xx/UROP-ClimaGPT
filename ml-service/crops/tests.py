"""
crops/tests.py

Tests for:
  - Crop CRUD (create, list, detail, update, delete)
  - Crop validation (harvest before sowing, missing fields, bad growth stage ID)
  - Farmer isolation (crop access gated through farm ownership)
  - Growth stage list endpoint
"""
from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from crops.models import GrowthStage

REGISTER_URL = '/api/auth/register/'
FARM_LIST_URL = '/api/farms/'
GROWTH_STAGES_URL = '/api/crops/growth-stages/'


def farm_crops_url(farm_id):
    return f'/api/farms/{farm_id}/crops/'


def crop_detail_url(pk):
    return f'/api/crops/{pk}/'


# ── Shared data ───────────────────────────────────────────────────────────────

_FARMER_A = {
    'full_name': 'Crop Farmer A',
    'email': 'cropa@crops.test',
    'phone_number': '+913333333333',
    'password': 'SecurePass123!',
    'confirm_password': 'SecurePass123!',
    'preferred_language': 'English',
}

_FARMER_B = {
    'full_name': 'Crop Farmer B',
    'email': 'cropb@crops.test',
    'phone_number': '+914444444444',
    'password': 'SecurePass123!',
    'confirm_password': 'SecurePass123!',
    'preferred_language': 'English',
}

_VALID_FARM = {
    'farm_name': 'Crop Test Farm',
    'farm_area': '3.0',
    'farm_area_unit': 'acre',
    'irrigation_type': 'drip',
    'latitude': '18.5204',
    'longitude': '73.8567',
}

_TODAY = date.today()
_HARVEST = _TODAY + timedelta(days=120)


# ---------------------------------------------------------------------------
# Crop CRUD
# ---------------------------------------------------------------------------

class CropCRUDTestCase(APITestCase):

    def setUp(self):
        self.stage = GrowthStage.objects.create(
            name='Seedling', order=1, crop_type=None
        )
        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.token = resp.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

        farm_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.farm_id = farm_resp.data['id']

        self.valid_crop = {
            'crop_name': 'Wheat',
            'crop_variety': 'HD 2967',
            'sowing_date': str(_TODAY),
            'expected_harvest_date': str(_HARVEST),
            'growth_stage': self.stage.id,
            'soil_type': 'loamy',
            'cultivation_method': 'conventional',
        }

    def test_create_crop_returns_201(self):
        resp = self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['crop_name'], 'Wheat')
        self.assertIn('growth_stage_detail', resp.data)

    def test_create_crop_without_optional_fields(self):
        """Only crop_name and sowing_date are mandatory."""
        data = {
            'crop_name': 'Rice',
            'sowing_date': str(_TODAY),
        }
        resp = self.client.post(farm_crops_url(self.farm_id), data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(resp.data['expected_harvest_date'])
        self.assertIsNone(resp.data['growth_stage'])

    def test_list_crops_for_farm(self):
        self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        resp = self.client.get(farm_crops_url(self.farm_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_multiple_crops_on_same_farm(self):
        self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        rice = {**self.valid_crop, 'crop_name': 'Rice', 'crop_variety': 'Pusa 1121'}
        self.client.post(farm_crops_url(self.farm_id), rice, format='json')
        resp = self.client.get(farm_crops_url(self.farm_id))
        self.assertEqual(len(resp.data), 2)

    def test_get_crop_detail(self):
        create_resp = self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        crop_id = create_resp.data['id']
        resp = self.client.get(crop_detail_url(crop_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['crop_name'], 'Wheat')

    def test_update_crop(self):
        create_resp = self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        crop_id = create_resp.data['id']
        resp = self.client.put(
            crop_detail_url(crop_id),
            {'crop_name': 'Barley'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['crop_name'], 'Barley')

    def test_delete_crop(self):
        create_resp = self.client.post(farm_crops_url(self.farm_id), self.valid_crop, format='json')
        crop_id = create_resp.data['id']
        resp = self.client.delete(crop_detail_url(crop_id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        get_resp = self.client.get(crop_detail_url(crop_id))
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_crop_list_returns_401(self):
        self.client.credentials()
        resp = self.client.get(farm_crops_url(self.farm_id))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Crop Validation
# ---------------------------------------------------------------------------

class CropValidationTestCase(APITestCase):

    def setUp(self):
        self.stage = GrowthStage.objects.create(
            name='Vegetative', order=2, crop_type=None
        )
        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp.data['token']}")
        farm_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.farm_id = farm_resp.data['id']

    def test_harvest_same_as_sowing_rejected(self):
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'crop_name': 'Corn', 'sowing_date': str(_TODAY),
             'expected_harvest_date': str(_TODAY), 'growth_stage': self.stage.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_harvest_before_sowing_rejected(self):
        yesterday = str(_TODAY - timedelta(days=1))
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'crop_name': 'Corn', 'sowing_date': str(_TODAY),
             'expected_harvest_date': yesterday, 'growth_stage': self.stage.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expected_harvest_date', str(resp.data))

    def test_missing_crop_name_rejected(self):
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'sowing_date': str(_TODAY), 'growth_stage': self.stage.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_sowing_date_rejected(self):
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'crop_name': 'Wheat', 'growth_stage': self.stage.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_growth_stage_id_rejected(self):
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'crop_name': 'Wheat', 'sowing_date': str(_TODAY), 'growth_stage': 999999},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_soil_type_rejected(self):
        resp = self.client.post(
            farm_crops_url(self.farm_id),
            {'crop_name': 'Wheat', 'sowing_date': str(_TODAY), 'soil_type': 'moon_dust'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_access_crops_on_nonexistent_farm_returns_404(self):
        resp = self.client.get(farm_crops_url(99999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Crop Isolation
# ---------------------------------------------------------------------------

class CropIsolationTestCase(APITestCase):
    """
    Farmer B cannot see, update, or delete Farmer A's crops,
    nor add crops to Farmer A's farm.
    """

    def setUp(self):
        self.stage = GrowthStage.objects.create(
            name='Flowering', order=3, crop_type=None
        )
        resp_a = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        resp_b = self.client.post(REGISTER_URL, _FARMER_B, format='json')
        self.token_a = resp_a.data['token']
        self.token_b = resp_b.data['token']

        # Farmer A creates farm + crop
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a}')
        farm_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.farm_a_id = farm_resp.data['id']

        crop_resp = self.client.post(
            farm_crops_url(self.farm_a_id),
            {'crop_name': 'Wheat', 'sowing_date': str(_TODAY), 'growth_stage': self.stage.id},
            format='json',
        )
        self.crop_a_id = crop_resp.data['id']

        # Switch to Farmer B
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_b}')

    def test_farmer_b_cannot_list_farmer_a_crops(self):
        resp = self.client.get(farm_crops_url(self.farm_a_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_get_farmer_a_crop(self):
        resp = self.client.get(crop_detail_url(self.crop_a_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_update_farmer_a_crop(self):
        resp = self.client.put(
            crop_detail_url(self.crop_a_id),
            {'crop_name': 'Hijacked'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_delete_farmer_a_crop(self):
        resp = self.client.delete(crop_detail_url(self.crop_a_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_add_crop_to_farmer_a_farm(self):
        resp = self.client.post(
            farm_crops_url(self.farm_a_id),
            {'crop_name': 'Intrusion', 'sowing_date': str(_TODAY)},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Growth Stage List
# ---------------------------------------------------------------------------

class GrowthStageListTestCase(APITestCase):

    def setUp(self):
        GrowthStage.objects.create(name='Seedling', order=1, crop_type=None)
        GrowthStage.objects.create(name='Vegetative', order=2, crop_type=None)
        GrowthStage.objects.create(name='Tillering', order=2, crop_type='wheat')

        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp.data['token']}")

    def test_returns_all_stages(self):
        resp = self.client.get(GROWTH_STAGES_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 3)

    def test_filter_by_crop_type_includes_generic(self):
        resp = self.client.get(f'{GROWTH_STAGES_URL}?crop_type=wheat')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [s['name'] for s in resp.data]
        self.assertIn('Tillering', names)   # wheat-specific
        self.assertIn('Seedling', names)    # generic
