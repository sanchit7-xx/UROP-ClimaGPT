"""
farms/tests.py

Tests for:
  - Farm CRUD (create, list, detail, update, delete)
  - Farm validation (invalid lat, invalid lng, zero/negative area, bad irrigation type)
  - Farmer isolation (Farmer B cannot see/edit/delete Farmer A's farms)
  - Dashboard endpoint
"""
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register/'
FARM_LIST_URL = '/api/farms/'
DASHBOARD_URL = '/api/dashboard/'


def farm_detail_url(pk):
    return f'/api/farms/{pk}/'


def farm_crops_url(farm_id):
    return f'/api/farms/{farm_id}/crops/'


# ── Shared test data ──────────────────────────────────────────────────────────

_FARMER_A = {
    'full_name': 'Farm Farmer A',
    'email': 'farma@farms.test',
    'phone_number': '+911111111111',
    'password': 'SecurePass123!',
    'confirm_password': 'SecurePass123!',
    'preferred_language': 'English',
}

_FARMER_B = {
    'full_name': 'Farm Farmer B',
    'email': 'farmb@farms.test',
    'phone_number': '+912222222222',
    'password': 'SecurePass123!',
    'confirm_password': 'SecurePass123!',
    'preferred_language': 'English',
}

_VALID_FARM = {
    'farm_name': 'Wheat Farm Alpha',
    'farm_area': '5.50',
    'farm_area_unit': 'acre',
    'irrigation_type': 'borewell',
    'latitude': '18.520400',
    'longitude': '73.856700',
    'state': 'Maharashtra',
    'district': 'Pune',
}


# ---------------------------------------------------------------------------
# Farm CRUD
# ---------------------------------------------------------------------------

class FarmCRUDTestCase(APITestCase):

    def setUp(self):
        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.token = resp.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_create_farm_returns_201(self):
        resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['farm_name'], 'Wheat Farm Alpha')
        self.assertIn('id', resp.data)

    def test_list_returns_own_farms_only(self):
        self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        resp = self.client.get(FARM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_create_multiple_farms(self):
        """One farmer can own multiple farms."""
        self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.client.post(FARM_LIST_URL, {**_VALID_FARM, 'farm_name': 'Rice Farm Beta'}, format='json')
        resp = self.client.get(FARM_LIST_URL)
        self.assertEqual(len(resp.data), 2)

    def test_retrieve_farm_detail(self):
        create_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        farm_id = create_resp.data['id']
        resp = self.client.get(farm_detail_url(farm_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['farm_name'], 'Wheat Farm Alpha')

    def test_update_farm(self):
        create_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        farm_id = create_resp.data['id']
        resp = self.client.put(
            farm_detail_url(farm_id),
            {'farm_name': 'Renamed Farm', 'farm_area': '7.0', 'farm_area_unit': 'ha',
             'irrigation_type': 'drip', 'latitude': '18.5204', 'longitude': '73.8567'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['farm_name'], 'Renamed Farm')

    def test_partial_update_farm(self):
        create_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        farm_id = create_resp.data['id']
        resp = self.client.put(
            farm_detail_url(farm_id),
            {'farm_name': 'Partial Update Farm'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['farm_name'], 'Partial Update Farm')

    def test_delete_farm(self):
        create_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        farm_id = create_resp.data['id']
        resp = self.client.delete(farm_detail_url(farm_id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        # Confirm it's gone
        get_resp = self.client.get(farm_detail_url(farm_id))
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_returns_401(self):
        self.client.credentials()
        resp = self.client.get(FARM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Farm Validation
# ---------------------------------------------------------------------------

class FarmValidationTestCase(APITestCase):

    def setUp(self):
        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp.data['token']}")

    def _post(self, **overrides):
        return self.client.post(FARM_LIST_URL, {**_VALID_FARM, **overrides}, format='json')

    def test_latitude_above_90_rejected(self):
        resp = self._post(latitude='91.0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_latitude_below_minus_90_rejected(self):
        resp = self._post(latitude='-91.0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_latitude_boundary_90_accepted(self):
        resp = self._post(latitude='90.0')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_latitude_boundary_minus_90_accepted(self):
        resp = self._post(latitude='-90.0')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_longitude_above_180_rejected(self):
        resp = self._post(longitude='181.0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_longitude_below_minus_180_rejected(self):
        resp = self._post(longitude='-181.0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_longitude_boundary_180_accepted(self):
        resp = self._post(longitude='180.0')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_area_zero_rejected(self):
        resp = self._post(farm_area='0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_area_negative_rejected(self):
        resp = self._post(farm_area='-2.5')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_irrigation_type_rejected(self):
        resp = self._post(irrigation_type='rocket_powered')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_area_unit_rejected(self):
        resp = self._post(farm_area_unit='lightyear')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_latitude_rejected(self):
        data = {k: v for k, v in _VALID_FARM.items() if k != 'latitude'}
        resp = self.client.post(FARM_LIST_URL, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_longitude_rejected(self):
        data = {k: v for k, v in _VALID_FARM.items() if k != 'longitude'}
        resp = self.client.post(FARM_LIST_URL, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Farmer Isolation
# ---------------------------------------------------------------------------

class FarmIsolationTestCase(APITestCase):
    """
    Ensures Farmer B cannot list, read, update, or delete Farmer A's farms.
    We return 404 (not 403) to prevent farm-ID enumeration attacks.
    """

    def setUp(self):
        resp_a = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        resp_b = self.client.post(REGISTER_URL, _FARMER_B, format='json')
        self.token_a = resp_a.data['token']
        self.token_b = resp_b.data['token']

        # Farmer A creates a farm
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a}')
        create_resp = self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        self.farm_a_id = create_resp.data['id']

        # Switch to Farmer B
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_b}')

    def test_farmer_b_list_shows_empty(self):
        resp = self.client.get(FARM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_farmer_b_cannot_read_farmer_a_farm(self):
        resp = self.client.get(farm_detail_url(self.farm_a_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_update_farmer_a_farm(self):
        resp = self.client.put(
            farm_detail_url(self.farm_a_id),
            {**_VALID_FARM, 'farm_name': 'Hijacked'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_farmer_b_cannot_delete_farmer_a_farm(self):
        resp = self.client.delete(farm_detail_url(self.farm_a_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardTestCase(APITestCase):

    def setUp(self):
        resp = self.client.post(REGISTER_URL, _FARMER_A, format='json')
        self.token = resp.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_dashboard_returns_200(self):
        resp = self.client.get(DASHBOARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dashboard_contains_farmer_info(self):
        resp = self.client.get(DASHBOARD_URL)
        self.assertIn('farmer', resp.data)
        self.assertEqual(resp.data['farmer']['full_name'], 'Farm Farmer A')

    def test_dashboard_summary_reflects_farm_count(self):
        self.client.post(FARM_LIST_URL, _VALID_FARM, format='json')
        resp = self.client.get(DASHBOARD_URL)
        self.assertEqual(resp.data['summary']['total_farms'], 1)

    def test_dashboard_unauthenticated_returns_401(self):
        self.client.credentials()
        resp = self.client.get(DASHBOARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
