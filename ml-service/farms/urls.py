"""
farms/urls.py

URL patterns for farms, including the nested crop list/create route.
Mounted at /api/farms/ in config/urls.py.
"""
from django.urls import path

from crops.views import FarmCropListCreateView

from .views import FarmDetailView, FarmListCreateView

urlpatterns = [
    # /api/farms/
    path('', FarmListCreateView.as_view(), name='farm-list-create'),

    # /api/farms/<id>/
    path('<int:pk>/', FarmDetailView.as_view(), name='farm-detail'),

    # /api/farms/<farm_id>/crops/   (nested — crop list + create for a farm)
    path('<int:farm_id>/crops/', FarmCropListCreateView.as_view(), name='farm-crop-list-create'),
]
