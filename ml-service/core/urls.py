"""
core/urls.py

Health-check endpoint — intentionally public, no authentication required.
Used by deployment health checks and monitoring tools.
"""
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """
    GET /api/health/

    Returns service name and status. Always 200 when the Django process
    is running. Does NOT check database connectivity in Stage 1.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'service': 'ClimaGPT Django Service',
            'status': 'healthy',
        })


urlpatterns = [
    path('', HealthView.as_view(), name='health'),
]
