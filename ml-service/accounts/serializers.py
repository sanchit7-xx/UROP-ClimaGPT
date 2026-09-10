"""
accounts/serializers.py

Serializers for:
  - Farmer registration   (RegisterSerializer)
  - Farmer login          (LoginSerializer)
  - Farmer profile        (FarmerProfileSerializer)

Validation rules:
  - Email must be unique (case-insensitive)
  - Phone: 7-15 digits, optional leading +
  - Password: Django's built-in validators (min 8 chars, not common, etc.)
  - Passwords must match
"""
import re

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import FarmerProfile, GenderChoices

# E.164-ish: optional leading +, then 7–15 digits
PHONE_REGEX = re.compile(r'^\+?[0-9]{7,15}$')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    """
    Handles Step 1 (Account) + Step 2 (Farmer Profile) of the onboarding flow.
    Creates a Django User + FarmerProfile + DRF Token atomically.
    """
    # ── Account fields ────────────────────────────────────────────────────
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    # ── Farmer profile fields ─────────────────────────────────────────────
    preferred_language = serializers.CharField(max_length=50, default='English')
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    district = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    village = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    age = serializers.IntegerField(min_value=1, max_value=120, required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[('', '')] + GenderChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    # ── Field-level validation ────────────────────────────────────────────

    def validate_email(self, value):
        normalised = value.lower().strip()
        if User.objects.filter(email__iexact=normalised).exists():
            raise serializers.ValidationError(
                'An account with this email address already exists.'
            )
        return normalised

    def validate_phone_number(self, value):
        value = value.strip()
        if not PHONE_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (7–15 digits, optional leading +).'
            )
        if FarmerProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                'This phone number is already registered.'
            )
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    # ── Object-level validation ───────────────────────────────────────────

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )
        return attrs

    # ── Create ───────────────────────────────────────────────────────────

    def create(self, validated_data):
        validated_data.pop('confirm_password')

        profile_fields = {
            'full_name': validated_data.pop('full_name'),
            'phone_number': validated_data.pop('phone_number'),
            'preferred_language': validated_data.pop('preferred_language', 'English'),
            'state': validated_data.pop('state', '') or '',
            'district': validated_data.pop('district', '') or '',
            'village': validated_data.pop('village', '') or '',
            'age': validated_data.pop('age', None),
            'gender': validated_data.pop('gender', None) or None,
        }

        # Use email as username so Django's auth.authenticate works with email
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
        )
        FarmerProfile.objects.create(user=user, **profile_fields)
        token, _ = Token.objects.get_or_create(user=user)
        return user, token


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# ---------------------------------------------------------------------------
# Farmer Profile (read + update)
# ---------------------------------------------------------------------------

class FarmerProfileSerializer(serializers.ModelSerializer):
    """Serializes FarmerProfile for GET and PUT /api/farmer/profile/."""
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = FarmerProfile
        fields = [
            'id',
            'email',
            'full_name',
            'phone_number',
            'preferred_language',
            'state',
            'district',
            'village',
            'age',
            'gender',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'email', 'created_at', 'updated_at']

    def validate_phone_number(self, value):
        value = value.strip()
        if not PHONE_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (7–15 digits, optional leading +).'
            )
        # Allow the same farmer to keep their own number
        request = self.context.get('request')
        qs = FarmerProfile.objects.filter(phone_number=value)
        if request and request.user.is_authenticated:
            qs = qs.exclude(user=request.user)
        if qs.exists():
            raise serializers.ValidationError(
                'This phone number is already registered to another account.'
            )
        return value
