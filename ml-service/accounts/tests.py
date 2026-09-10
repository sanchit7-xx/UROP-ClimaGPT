"""
accounts/tests.py

Tests for:
  - Registration (success, duplicate email, duplicate phone, bad password,
                  phone format, password mismatch, missing fields)
  - Login (success, wrong password, non-existent email)
  - Farmer profile (GET authenticated, GET unauthenticated, PUT update,
                    farmer isolation)
"""
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register/'
LOGIN_URL = '/api/auth/login/'
PROFILE_URL = '/api/farmer/profile/'

_BASE = {
    'full_name': 'Test Farmer',
    'email': 'farmer@climagpt.test',
    'phone_number': '+919876543210',
    'password': 'SecurePass123!',
    'confirm_password': 'SecurePass123!',
    'preferred_language': 'English',
    'state': 'Maharashtra',
    'district': 'Pune',
    'village': 'Hadapsar',
}


def _reg(**overrides):
    return {**_BASE, **overrides}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegistrationTestCase(APITestCase):

    def test_success_returns_201_with_token_and_profile(self):
        resp = self.client.post(REGISTER_URL, _reg(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', resp.data)
        self.assertIn('farmer', resp.data)
        self.assertEqual(resp.data['farmer']['full_name'], 'Test Farmer')
        self.assertEqual(resp.data['farmer']['email'], 'farmer@climagpt.test')

    def test_duplicate_email_rejected(self):
        self.client.post(REGISTER_URL, _reg(), format='json')
        # Same email, different phone
        resp = self.client.post(REGISTER_URL, _reg(phone_number='+911234567890'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('details', resp.data)

    def test_duplicate_phone_rejected(self):
        self.client.post(REGISTER_URL, _reg(), format='json')
        # Different email, same phone
        resp = self.client.post(REGISTER_URL, _reg(email='other@climagpt.test'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch_rejected(self):
        resp = self.client.post(
            REGISTER_URL,
            _reg(confirm_password='NotTheSame!'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_rejected(self):
        resp = self.client.post(
            REGISTER_URL,
            _reg(password='123', confirm_password='123'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_phone_format_rejected(self):
        resp = self.client.post(
            REGISTER_URL,
            _reg(phone_number='not-a-phone'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_fields_rejected(self):
        resp = self.client.post(REGISTER_URL, {'email': 'x@x.com'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email_format_rejected(self):
        resp = self.client.post(REGISTER_URL, _reg(email='not-an-email'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_optional_fields_accepted_when_absent(self):
        """age and gender are optional — registration should succeed without them."""
        data = {k: v for k, v in _reg().items() if k not in ('age', 'gender')}
        resp = self.client.post(REGISTER_URL, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginTestCase(APITestCase):

    def setUp(self):
        resp = self.client.post(REGISTER_URL, _reg(), format='json')
        self.token = resp.data['token']

    def test_login_success_returns_token(self):
        resp = self.client.post(
            LOGIN_URL,
            {'email': 'farmer@climagpt.test', 'password': 'SecurePass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('token', resp.data)
        self.assertIn('farmer', resp.data)

    def test_wrong_password_returns_401(self):
        resp = self.client.post(
            LOGIN_URL,
            {'email': 'farmer@climagpt.test', 'password': 'WrongPassword!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data['error'], 'Unauthorized')

    def test_nonexistent_email_returns_401(self):
        resp = self.client.post(
            LOGIN_URL,
            {'email': 'nobody@climagpt.test', 'password': 'SecurePass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_credentials_returns_400(self):
        resp = self.client.post(LOGIN_URL, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Farmer Profile
# ---------------------------------------------------------------------------

class FarmerProfileTestCase(APITestCase):

    def setUp(self):
        resp = self.client.post(REGISTER_URL, _reg(), format='json')
        self.token = resp.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_get_own_profile(self):
        resp = self.client.get(PROFILE_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['full_name'], 'Test Farmer')
        self.assertEqual(resp.data['email'], 'farmer@climagpt.test')

    def test_unauthenticated_get_returns_401(self):
        self.client.credentials()  # remove token
        resp = self.client.get(PROFILE_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_full_name(self):
        resp = self.client.put(
            PROFILE_URL,
            {'full_name': 'Updated Farmer Name'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['full_name'], 'Updated Farmer Name')

    def test_update_preferred_language(self):
        resp = self.client.put(
            PROFILE_URL,
            {'preferred_language': 'Hindi'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['preferred_language'], 'Hindi')

    def test_profile_endpoint_returns_own_profile_only(self):
        """
        Farmer B's token must return Farmer B's profile, not Farmer A's.
        Both farmers call the same endpoint — isolation is enforced via request.user.
        """
        farmer_b_data = _reg(
            email='farmerb@climagpt.test',
            phone_number='+919999999999',
            full_name='Farmer B',
        )
        resp_b = self.client.post(REGISTER_URL, farmer_b_data, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp_b.data['token']}")

        resp = self.client.get(PROFILE_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['email'], 'farmerb@climagpt.test')
        self.assertNotEqual(resp.data['email'], 'farmer@climagpt.test')
