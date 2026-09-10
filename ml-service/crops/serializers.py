"""
crops/serializers.py

Serializers for:
  GrowthStage   — read-only list view
  CropProfile   — full CRUD with date validation
"""
from rest_framework import serializers

from .models import CropProfile, GrowthStage


class GrowthStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrowthStage
        fields = ['id', 'name', 'order', 'description', 'crop_type']
        read_only_fields = ['id']


class CropProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for CropProfile.

    'growth_stage' (write) accepts an integer ID.
    'growth_stage_detail' (read-only) returns the full stage object.

    Validation:
      - crop_name is required.
      - sowing_date is required.
      - expected_harvest_date, if provided, must be AFTER sowing_date.
      - growth_stage FK is validated automatically by DRF (bad ID → 400).
    """
    growth_stage_detail = GrowthStageSerializer(source='growth_stage', read_only=True)

    class Meta:
        model = CropProfile
        fields = [
            'id',
            'farm',
            'crop_name',
            'crop_variety',
            'sowing_date',
            'expected_harvest_date',
            'growth_stage',
            'growth_stage_detail',
            'soil_type',
            'cultivation_method',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'farm', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Ensure harvest date is always after sowing date."""
        # For updates, fall back to the existing instance values
        sowing = attrs.get(
            'sowing_date',
            getattr(self.instance, 'sowing_date', None),
        )
        harvest = attrs.get(
            'expected_harvest_date',
            getattr(self.instance, 'expected_harvest_date', None),
        )

        if sowing and harvest and harvest <= sowing:
            raise serializers.ValidationError({
                'expected_harvest_date': (
                    'Expected harvest date must be strictly after the sowing date.'
                ),
            })
        return attrs
