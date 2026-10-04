"""
soil/views.py

API Views for Stage 4: Soil Moisture & Farm Environmental State.

Endpoints:
    POST /api/soil-moisture/sensor/             — Ingest sensor reading
    GET  /api/soil-moisture/farms/<id>/current/ — Latest soil moisture
    GET  /api/soil-moisture/farms/<id>/history/ — Historical soil moisture
    GET  /api/environment/farms/<id>/state/     — Complete environmental state
"""
import logging
from datetime import datetime, date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from farms.models import Farm
from .models import SoilMoisture
from .serializers import SoilMoistureSerializer, SensorIngestionSerializer
from .services import (
    SensorSoilMoistureProvider,
    EnvironmentalStateService,
)

logger = logging.getLogger(__name__)


class FarmOwnershipMixin:
    """Mixin enforcing that the requested farm belongs to the requesting farmer."""
    permission_classes = [IsAuthenticated]

    def get_farm(self, farm_id: int) -> Farm:
        farmer_profile = getattr(self.request.user, 'farmer_profile', None)
        if not farmer_profile:
            raise PermissionDenied("You must complete farmer registration to access farm data.")
        return get_object_or_404(Farm, pk=farm_id, farmer=farmer_profile)


class SensorIngestionView(APIView):
    """
    POST /api/soil-moisture/sensor/

    Ingest an in-situ or telemetry soil moisture reading.
    Validates authentication, farm ownership, numeric bounds, non-negative depth,
    valid timestamp, and prevents duplicates.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SensorIngestionSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reading = serializer.save()
        output_serializer = SoilMoistureSerializer(reading)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class CurrentSoilMoistureView(FarmOwnershipMixin, APIView):
    """
    GET /api/soil-moisture/farms/<farm_id>/current/

    Returns the latest valid soil moisture reading for this farm.
    If no readings exist, returns 404 with clear message and supported future sources.
    Never fabricates or estimates dummy values.
    """

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        latest_reading = SoilMoisture.objects.filter(farm=farm).order_by('-timestamp').first()

        if not latest_reading:
            return Response(
                {
                    "farm_id": farm.id,
                    "available": False,
                    "detail": "Soil moisture data is not available for this farm.",
                    "possible_sources": ["SENSOR", "SATELLITE", "REANALYSIS"],
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SoilMoistureSerializer(latest_reading)
        data = serializer.data
        data["available"] = True
        return Response(data, status=status.HTTP_200_OK)


class SoilMoistureHistoryView(FarmOwnershipMixin, APIView):
    """
    GET /api/soil-moisture/farms/<farm_id>/history/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&depth=20

    Returns historical soil moisture records for the specified farm.
    Only returns records belonging to the authenticated farmer.
    """

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        qs = SoilMoisture.objects.filter(farm=farm)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        depth_param = request.query_params.get('depth')

        if start_date_str:
            try:
                start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                qs = qs.filter(timestamp__date__gte=start_d)
            except ValueError:
                return Response(
                    {"detail": "Invalid start_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                qs = qs.filter(timestamp__date__lte=end_d)
            except ValueError:
                return Response(
                    {"detail": "Invalid end_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if depth_param:
            try:
                depth_val = int(depth_param)
                if depth_val < 0:
                    return Response(
                        {"detail": "Depth parameter must be non-negative."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                qs = qs.filter(depth=depth_val)
            except ValueError:
                return Response(
                    {"detail": "Invalid depth parameter. Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        readings = qs.order_by('timestamp')
        serializer = SoilMoistureSerializer(readings, many=True)

        return Response({
            "farm_id": farm.id,
            "count": len(readings),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


class EnvironmentalStateView(FarmOwnershipMixin, APIView):
    """
    GET /api/environment/farms/<farm_id>/state/

    Returns the latest consolidated environmental conditions for the farm:
    - Current soil moisture
    - Current weather parameters (temp, humidity, recent rainfall, ET)
    - Farm/crop soil type

    STRICT: Describes current state only. No irrigation recommendations.
    """

    def get(self, request, farm_id):
        farm = self.get_farm(farm_id)
        state = EnvironmentalStateService.get_farm_environmental_state(farm)
        return Response(state, status=status.HTTP_200_OK)
