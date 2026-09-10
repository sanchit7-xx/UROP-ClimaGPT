"""
farms/serializers.py

FarmSerializer — validates and serializes Farm objects.

Validation:
  - latitude:  -90 ≤ value ≤ 90
  - longitude: -180 ≤ value ≤ 180
  - farm_area: must be > 0
  - farm_area_unit: must be a valid AreaUnitChoices value
  - irrigation_type: must be a valid IrrigationTypeChoices value
"""
from rest_framework import serializers

from .models import AreaUnitChoices, Farm, IrrigationTypeChoices


class FarmSerializer(serializers.ModelSerializer):
    """
    Used for all Farm CRUD operations.
    The 'farmer' field is excluded from the serializer and injected by the
    view (serializer.save(farmer=...)) to enforce ownership.
    """

    class Meta:
        model = Farm
        fields = [
            'id',
            'farm_name',
            'farm_area',
            'farm_area_unit',
            'irrigation_type',
            # Primary location
            'latitude',
            'longitude',
            # Supplementary address
            'village',
            'locality',
            'city',
            'district',
            'state',
            'country',
            'postal_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # ── Field-level validators ────────────────────────────────────────────

    def validate_latitude(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError(
                'Latitude must be between -90 and 90.'
            )
        return value

    def validate_longitude(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError(
                'Longitude must be between -180 and 180.'
            )
        return value

    def validate_farm_area(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Farm area must be greater than 0.'
            )
        return value
