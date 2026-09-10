"""
accounts/urls.py

URL patterns for the accounts app.
These are imported as named lists in config/urls.py to be mounted at
specific prefixes (/api/auth/ and /api/farmer/).
"""
from django.urls import path

from .views import FarmerProfileView, LoginView, RegisterView

# Mounted at /api/auth/ in config/urls.py
auth_patterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
]

# Mounted at /api/farmer/ in config/urls.py
farmer_patterns = [
    path('profile/', FarmerProfileView.as_view(), name='farmer-profile'),
]
