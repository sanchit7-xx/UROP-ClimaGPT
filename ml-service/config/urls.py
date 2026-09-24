"""
URL configuration for ClimaGPT Django project.

API route layout:
    /api/health/                    — Service health check (public)
    /api/auth/register/             — Farmer registration
    /api/auth/login/                — Farmer login → token
    /api/farmer/profile/            — Farmer profile (GET / PUT)
    /api/farms/                     — Farm list / create
    /api/farms/<id>/                — Farm detail / update / delete
    /api/farms/<farm_id>/crops/     — Crop list / create for a farm
    /api/crops/<id>/                — Crop detail / update / delete
    /api/crops/growth-stages/       — List available growth stages
    /api/dashboard/                 — Farmer dashboard summary
"""
from django.contrib import admin
from django.urls import path, include

from accounts.urls import auth_patterns, farmer_patterns
from farms.views import DashboardView

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # ── Public ──────────────────────────────────────────────────────────────
    path('api/health/', include('core.urls')),

    # ── Authentication ───────────────────────────────────────────────────────
    path('api/auth/', include(auth_patterns)),

    # ── Farmer profile ───────────────────────────────────────────────────────
    path('api/farmer/', include(farmer_patterns)),

    # ── Farms (includes nested /crops/ route) ────────────────────────────────
    path('api/farms/', include('farms.urls')),

    # ── Crop detail & growth stages ──────────────────────────────────────────
    path('api/crops/', include('crops.urls')),

    # ── Dashboard ────────────────────────────────────────────────────────────
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('', include('weather.urls')),
]
