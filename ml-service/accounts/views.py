"""
accounts/views.py

API views for:
  POST /api/auth/register/   — create account + profile → returns token
  POST /api/auth/login/      — authenticate → returns token
  GET  /api/farmer/profile/  — retrieve own profile
  PUT  /api/farmer/profile/  — update own profile (partial allowed)
"""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import FarmerProfileSerializer, LoginSerializer, RegisterSerializer


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterView(APIView):
    """
    POST /api/auth/register/

    Onboarding Step 1+2: create a Django User, FarmerProfile, and auth Token
    in a single request.  Returns the token immediately so the client can
    proceed to subsequent onboarding steps without a separate login.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user, token = serializer.save()
        return Response(
            {
                'message': 'Registration successful. Welcome to ClimaGPT!',
                'token': token.key,
                'farmer': FarmerProfileSerializer(user.farmer_profile).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginView(APIView):
    """
    POST /api/auth/login/

    Authenticates a farmer by email + password and returns their DRF token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        password = serializer.validated_data['password']

        # Username == email (set during registration)
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {'error': 'Unauthorized', 'details': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'message': 'Login successful.',
            'token': token.key,
            'farmer': FarmerProfileSerializer(user.farmer_profile).data,
        })


# ---------------------------------------------------------------------------
# Farmer Profile
# ---------------------------------------------------------------------------

class FarmerProfileView(APIView):
    """
    GET  /api/farmer/profile/  — returns the authenticated farmer's profile
    PUT  /api/farmer/profile/  — updates (partial) the authenticated farmer's profile

    Authorization: a farmer can ONLY access their OWN profile.
    The profile is derived directly from request.user, so no ID lookup is
    needed and no cross-farmer access is possible.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = FarmerProfileSerializer(
            request.user.farmer_profile,
            context={'request': request},
        )
        return Response(serializer.data)

    def put(self, request):
        serializer = FarmerProfileSerializer(
            request.user.farmer_profile,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(serializer.data)
