"""
crops/views.py

API views for:
  GET  /api/farms/<farm_id>/crops/   — list crops for a farm
  POST /api/farms/<farm_id>/crops/   — add a crop to a farm
  GET  /api/crops/<id>/              — crop detail
  PUT  /api/crops/<id>/              — update crop
  DELETE /api/crops/<id>/            — delete crop
  GET  /api/crops/growth-stages/     — list all available growth stages

Authorization:
  Crop access is gated through farm ownership.
  The queryset filter `farm__farmer=request.user.farmer_profile` ensures
  that a farmer can never read/write another farmer's crops.
  We return 404 (not 403) for the same ID-enumeration reason as farms.
"""
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from farms.models import Farm

from .models import CropProfile, GrowthStage
from .serializers import CropProfileSerializer, GrowthStageSerializer


# ---------------------------------------------------------------------------
# Crops nested under a farm: /api/farms/<farm_id>/crops/
# ---------------------------------------------------------------------------

class FarmCropListCreateView(APIView):
    """
    GET  /api/farms/<farm_id>/crops/
    POST /api/farms/<farm_id>/crops/
    """
    permission_classes = [IsAuthenticated]

    def _get_farm(self, farm_id, request):
        """Retrieve farm, returning 404 if it doesn't belong to this farmer."""
        return get_object_or_404(
            Farm, pk=farm_id, farmer=request.user.farmer_profile
        )

    def get(self, request, farm_id):
        farm = self._get_farm(farm_id, request)
        crops = farm.crops.select_related('growth_stage').all()
        return Response(CropProfileSerializer(crops, many=True).data)

    def post(self, request, farm_id):
        farm = self._get_farm(farm_id, request)
        serializer = CropProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(farm=farm)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Crop detail: /api/crops/<id>/
# ---------------------------------------------------------------------------

class CropDetailView(APIView):
    """
    GET    /api/crops/<id>/
    PUT    /api/crops/<id>/
    DELETE /api/crops/<id>/
    """
    permission_classes = [IsAuthenticated]

    def _get_crop(self, pk, request):
        """
        Retrieve crop by PK, verifying ownership through the
        farm → farmer chain.  Returns 404 if not found or not owned.
        """
        return get_object_or_404(
            CropProfile,
            pk=pk,
            farm__farmer=request.user.farmer_profile,
        )

    def get(self, request, pk):
        crop = self._get_crop(pk, request)
        return Response(CropProfileSerializer(crop).data)

    def put(self, request, pk):
        crop = self._get_crop(pk, request)
        serializer = CropProfileSerializer(crop, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        crop = self._get_crop(pk, request)
        crop.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Growth stage reference list: /api/crops/growth-stages/
# ---------------------------------------------------------------------------

class GrowthStageListView(APIView):
    """
    GET /api/crops/growth-stages/?crop_type=<name>

    Returns available growth stages.
    Without ?crop_type, returns all generic stages (crop_type=None).
    With ?crop_type=wheat, returns wheat-specific + generic stages.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not GrowthStage.objects.exists():
            DEFAULT_STAGES = [
                {"name": "Sowing / Germination", "order": 1, "description": "Initial seed planting and germination phase."},
                {"name": "Seedling", "order": 2, "description": "Early emergence and initial leaf development."},
                {"name": "Vegetative", "order": 3, "description": "Rapid stem elongation and canopy growth."},
                {"name": "Tillering / Branching", "order": 4, "description": "Development of side shoots and main branches."},
                {"name": "Flowering / Reproductive", "order": 5, "description": "Blossoming and pollination phase."},
                {"name": "Grain Filling / Pod Formation", "order": 6, "description": "Development and filling of grain or fruit."},
                {"name": "Maturity / Harvest", "order": 7, "description": "Final ripening and harvest ready."},
            ]
            for stage in DEFAULT_STAGES:
                GrowthStage.objects.get_or_create(name=stage["name"], defaults=stage)

        crop_type = request.query_params.get('crop_type')
        if crop_type:
            qs = GrowthStage.objects.filter(
                crop_type=crop_type
            ) | GrowthStage.objects.filter(crop_type__isnull=True)
            qs = qs.order_by('order')
        else:
            qs = GrowthStage.objects.all().order_by('order')

        return Response(GrowthStageSerializer(qs, many=True).data)
