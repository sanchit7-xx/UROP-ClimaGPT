"""
soil/serializers.py

Serializers for Stage 4 Soil Moisture & Sensor Ingestion.
"""
from rest_framework import serializers
from farms.models import Farm
from .models import (
    SoilMoisture,
    SoilMoistureSourceChoices,
    SoilMoistureUnitChoices,
)


class SoilMoistureSerializer(serializers.ModelSerializer):
    """
    Serializer for normalized SoilMoisture records.
    Includes human-readable confidence_level.
    """
    confidence_level = serializers.ReadOnlyField()
    farm_id = serializers.IntegerField(source='farm.id', read_only=True)

    class Meta:
        model = SoilMoisture
        fields = [
            'id',
            'farm_id',
            'latitude',
            'longitude',
            'timestamp',
            'moisture',
            'unit',
            'depth',
            'source',
            'confidence',
            'confidence_level',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'confidence_level', 'farm_id']


class SensorIngestionSerializer(serializers.Serializer):
    """
    Validates sensor ingestion payload:
    {
        "farm_id": 1,
        "moisture": 24.5,
        "unit": "PERCENT",
        "depth": 20,
        "timestamp": "2026-10-04T10:00:00Z",
        "confidence": 0.98
    }
    """
    farm_id = serializers.IntegerField(required=True)
    moisture = serializers.FloatField(required=True)
    unit = serializers.ChoiceField(
        choices=SoilMoistureUnitChoices.choices,
        default=SoilMoistureUnitChoices.PERCENT,
        required=False,
    )
    depth = serializers.IntegerField(
        default=20,
        min_value=0,
        required=False,
    )
    timestamp = serializers.DateTimeField(required=True)
    confidence = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.0,
        max_value=1.0,
        default=0.98,
    )

    def validate_moisture(self, value):
        """Validate moisture is within reasonable physical range."""
        if value < 0.0 or value > 100.0:
            raise serializers.ValidationError(
                f"Moisture value ({value}) must be between 0.0 and 100.0 for PERCENT unit."
            )
        return round(float(value), 2)

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        farmer_profile = getattr(user, 'farmer_profile', None)
        if not farmer_profile:
            raise serializers.ValidationError("Authenticated user has no farmer profile.")

        farm_id = attrs.get('farm_id')
        try:
            farm = Farm.objects.get(id=farm_id, farmer=farmer_profile)
        except Farm.DoesNotExist:
            raise serializers.ValidationError(
                {"farm_id": f"Farm with id {farm_id} does not exist or does not belong to you."}
            )

        attrs['farm'] = farm

        # Check for duplicate reading
        timestamp = attrs.get('timestamp')
        depth = attrs.get('depth', 20)
        source = SoilMoistureSourceChoices.SENSOR

        if SoilMoisture.objects.filter(
            farm=farm,
            timestamp=timestamp,
            depth=depth,
            source=source,
        ).exists():
            raise serializers.ValidationError(
                "A reading for this farm, timestamp, depth, and source already exists."
            )

        return attrs

    def create(self, validated_data):
        farm = validated_data['farm']
        return SoilMoisture.objects.create(
            farm=farm,
            latitude=farm.latitude,
            longitude=farm.longitude,
            timestamp=validated_data['timestamp'],
            moisture=validated_data['moisture'],
            unit=validated_data.get('unit', SoilMoistureUnitChoices.PERCENT),
            depth=validated_data.get('depth', 20),
            source=SoilMoistureSourceChoices.SENSOR,
            confidence=validated_data.get('confidence', 0.98),
        )
