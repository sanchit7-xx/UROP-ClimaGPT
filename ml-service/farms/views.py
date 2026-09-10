"""
farms/views.py

API views for:
  GET    /api/farms/                 — list own farms
  POST   /api/farms/                 — create farm (triggers Mapbox reverse geocoding)
  GET    /api/farms/<id>/            — farm detail
  PUT    /api/farms/<id>/            — update farm
  DELETE /api/farms/<id>/            — delete farm

  GET    /api/dashboard/             — dashboard summary (no weather data — Stage 2)

Ownership isolation:
  All queryset filters use farmer=request.user.farmer_profile, so farmers
  can NEVER see or modify another farmer's data.
"""
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import MapboxServiceError
from core.utilities import MapboxService

from .models import Farm
from .serializers import FarmSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Farm CRUD
# ---------------------------------------------------------------------------

class FarmListCreateView(APIView):
    """GET /api/farms/  and  POST /api/farms/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return only the authenticated farmer's farms."""
        farms = Farm.objects.filter(farmer=request.user.farmer_profile)
        return Response(FarmSerializer(farms, many=True).data)

    def post(self, request):
        """
        Create a new farm.

        After validation, we attempt Mapbox reverse geocoding to populate
        the supplementary address fields automatically.  If Mapbox is
        unavailable or not configured, farm creation still succeeds — the
        address fields will simply be empty (the client can supply them
        manually if needed).
        """
        serializer = FarmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Attempt reverse geocoding (best-effort — never blocks farm creation)
        address_patch = {}
        if settings.MAPBOX_ACCESS_TOKEN:
            try:
                mapbox = MapboxService()
                lat = float(serializer.validated_data['latitude'])
                lng = float(serializer.validated_data['longitude'])
                geocoded = mapbox.reverse_geocode(lat, lng)
                # Only fill address fields that the client didn't provide
                for key, value in geocoded.items():
                    if value and not serializer.validated_data.get(key):
                        address_patch[key] = value
            except (MapboxServiceError, Exception) as exc:
                logger.warning(
                    'Mapbox reverse geocoding skipped during farm creation: %s', exc
                )

        farm = serializer.save(
            farmer=request.user.farmer_profile,
            **address_patch,
        )
        return Response(FarmSerializer(farm).data, status=status.HTTP_201_CREATED)


class FarmDetailView(APIView):
    """GET/PUT/DELETE /api/farms/<id>/"""
    permission_classes = [IsAuthenticated]

    def _get_farm(self, pk, request):
        """
        Retrieve farm by PK, scoped to the authenticated farmer.
        Returns 404 (not 403) when the farm exists but belongs to
        another farmer — this prevents farm ID enumeration.
        """
        return get_object_or_404(
            Farm, pk=pk, farmer=request.user.farmer_profile
        )

    def get(self, request, pk):
        farm = self._get_farm(pk, request)
        return Response(FarmSerializer(farm).data)

    def put(self, request, pk):
        farm = self._get_farm(pk, request)
        serializer = FarmSerializer(farm, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        farm = self._get_farm(pk, request)
        farm.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(APIView):
    """
    GET /api/dashboard/

    Returns a summary of the authenticated farmer's profile, all their farms,
    and all crops per farm including current growth stage.

    Stage 1: NO weather data is returned.
    Stage 2 will extend this response with weather forecasts, crop risk
    assessments, and irrigation recommendations.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.farmer_profile
        farms = (
            Farm.objects
            .filter(farmer=profile)
            .prefetch_related('crops__growth_stage')
        )

        farm_list = []
        total_crops = 0

        for farm in farms:
            crops_data = []
            for crop in farm.crops.all():
                crops_data.append({
                    'id': crop.id,
                    'crop_name': crop.crop_name,
                    'crop_variety': crop.crop_variety,
                    'sowing_date': str(crop.sowing_date),
                    'expected_harvest_date': (
                        str(crop.expected_harvest_date)
                        if crop.expected_harvest_date else None
                    ),
                    'growth_stage': (
                        {
                            'id': crop.growth_stage.id,
                            'name': crop.growth_stage.name,
                            'order': crop.growth_stage.order,
                        }
                        if crop.growth_stage else None
                    ),
                    'soil_type': crop.soil_type,
                    'cultivation_method': crop.cultivation_method,
                })

            total_crops += len(crops_data)
            farm_list.append({
                'id': farm.id,
                'farm_name': farm.farm_name,
                'farm_area': str(farm.farm_area),
                'farm_area_unit': farm.farm_area_unit,
                'irrigation_type': farm.irrigation_type,
                'location': {
                    'latitude': str(farm.latitude),
                    'longitude': str(farm.longitude),
                    'village': farm.village,
                    'locality': farm.locality,
                    'city': farm.city,
                    'district': farm.district,
                    'state': farm.state,
                    'country': farm.country,
                    'postal_code': farm.postal_code,
                },
                'crops_count': len(crops_data),
                'crops': crops_data,
            })

        return Response({
            'farmer': {
                'id': profile.id,
                'full_name': profile.full_name,
                'email': profile.user.email,
                'phone_number': profile.phone_number,
                'preferred_language': profile.preferred_language,
                'state': profile.state,
                'district': profile.district,
            },
            'summary': {
                'total_farms': len(farm_list),
                'total_crops': total_crops,
                # Stage 2 will add: active_alerts, weather_warnings, etc.
            },
            'farms': farm_list,
        })
