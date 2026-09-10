"""
crops/urls.py

Mounted at /api/crops/ in config/urls.py.

Note: /api/farms/<farm_id>/crops/ is mounted in farms/urls.py
      because it's nested under the farm resource.
"""
from django.urls import path

from .views import CropDetailView, GrowthStageListView

urlpatterns = [
    # /api/crops/growth-stages/  — MUST be before <int:pk>/ to avoid collision
    path('growth-stages/', GrowthStageListView.as_view(), name='growth-stage-list'),

    # /api/crops/<id>/
    path('<int:pk>/', CropDetailView.as_view(), name='crop-detail'),
]
