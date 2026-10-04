"""
predictions/serializers.py

Serializers for Stage 5: AI Weather Prediction Models.
"""
from rest_framework import serializers
from .models import WeatherPrediction, ModelMetadata


class WeatherPredictionSerializer(serializers.ModelSerializer):
    """Serializes individual WeatherPrediction records."""
    timestamp = serializers.DateTimeField(source='target_timestamp')
    temperature = serializers.FloatField(source='temperature_prediction')
    rainfall = serializers.FloatField(source='rainfall_prediction')
    humidity = serializers.FloatField(source='humidity_prediction')
    wind_speed = serializers.FloatField(source='wind_speed_prediction')

    class Meta:
        model = WeatherPrediction
        fields = [
            'id',
            'timestamp',
            'temperature',
            'rainfall',
            'humidity',
            'wind_speed',
            'model_version',
            'prediction_timestamp',
        ]


class ModelMetadataSerializer(serializers.ModelSerializer):
    """Serializes ModelMetadata records for transparency and research reporting."""
    class Meta:
        model = ModelMetadata
        fields = [
            'id',
            'target',
            'model_name',
            'version',
            'trained_at',
            'training_start',
            'training_end',
            'test_start',
            'test_end',
            'sample_count',
            'train_samples',
            'val_samples',
            'test_samples',
            'baseline_mae',
            'baseline_rmse',
            'baseline_r2',
            'baseline_mbe',
            'model_mae',
            'model_rmse',
            'model_r2',
            'model_mbe',
            'features',
            'feature_importances',
            'is_active',
            'notes',
        ]
