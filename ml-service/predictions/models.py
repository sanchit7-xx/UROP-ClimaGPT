"""
predictions/models.py

Models for Stage 5: AI Weather Prediction Models.

Contains:
  - WeatherPrediction: Normalized ML weather predictions.
  - ModelMetadata: Research traceability, metrics, and training metadata.
"""
from django.db import models
from farms.models import Farm


class WeatherPrediction(models.Model):
    """
    Stores individual ML-generated weather predictions for a farm at a specific future timestamp.
    
    Distinct from:
      - OBSERVED WEATHER (recorded sensor/historical observations)
      - EXTERNAL FORECAST (Open-Meteo or external provider forecasts)
    """
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='weather_predictions',
        help_text="Farm for which this weather prediction was generated."
    )
    model_version = models.CharField(
        max_length=64,
        default='weather_v1',
        db_index=True,
        help_text="Model version identifier used to generate this prediction."
    )
    prediction_timestamp = models.DateTimeField(
        db_index=True,
        help_text="Timestamp when the prediction was generated/inferred."
    )
    target_timestamp = models.DateTimeField(
        db_index=True,
        help_text="Future timestamp for which this prediction applies."
    )
    temperature_prediction = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted air temperature in °C."
    )
    rainfall_prediction = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted rainfall/precipitation in mm."
    )
    humidity_prediction = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted relative humidity in %."
    )
    wind_speed_prediction = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted wind speed in km/h."
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="System timestamp when this record was saved."
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = 'weather_predictions'
        ordering = ['target_timestamp']
        unique_together = ('farm', 'model_version', 'target_timestamp')
        indexes = [
            models.Index(fields=['farm', 'target_timestamp']),
            models.Index(fields=['farm', 'model_version']),
        ]

    def __str__(self):
        return f"Prediction [Farm {self.farm_id}] target={self.target_timestamp} (T={self.temperature_prediction}°C, R={self.rainfall_prediction}mm)"


class ModelMetadata(models.Model):
    """
    Tracks trained ML model metadata, versioning, artifacts, and evaluation performance.
    
    Preserves research reproducibility by logging:
      - Training & test time windows
      - Train/Val/Test sample counts
      - Feature definitions
      - Baseline vs ML performance (MAE, RMSE, R², MBE)
    """
    farm = models.ForeignKey(
        Farm,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='trained_models',
        help_text="Farm ID if model was trained farm-specifically, or NULL for regional/global models."
    )
    target = models.CharField(
        max_length=50,
        help_text="Target variable (e.g., 'temperature', 'precipitation', 'relative_humidity', 'wind_speed')."
    )
    model_name = models.CharField(
        max_length=100,
        default='RandomForestRegressor',
        help_text="Machine learning model algorithm/class name."
    )
    version = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Unique model version tag (e.g. weather_temperature_v1)."
    )
    trained_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when training was executed."
    )
    training_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start timestamp of chronological training window."
    )
    training_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End timestamp of chronological training window."
    )
    test_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start timestamp of chronological test window."
    )
    test_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End timestamp of chronological test window."
    )
    sample_count = models.IntegerField(
        default=0,
        help_text="Total validated samples in the processed dataset."
    )
    train_samples = models.IntegerField(
        default=0,
        help_text="Number of samples in training split (70%)."
    )
    val_samples = models.IntegerField(
        default=0,
        help_text="Number of samples in validation split (15%)."
    )
    test_samples = models.IntegerField(
        default=0,
        help_text="Number of samples in test split (15%)."
    )
    # Baseline Metrics (Persistence / Last-Value)
    baseline_mae = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Absolute Error of Persistence baseline on test split."
    )
    baseline_rmse = models.FloatField(
        null=True,
        blank=True,
        help_text="Root Mean Squared Error of Persistence baseline on test split."
    )
    baseline_r2 = models.FloatField(
        null=True,
        blank=True,
        help_text="Coefficient of determination (R²) of Persistence baseline on test split."
    )
    baseline_mbe = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Bias Error of Persistence baseline on test split."
    )
    # ML Model Metrics
    model_mae = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Absolute Error of ML model on test split."
    )
    model_rmse = models.FloatField(
        null=True,
        blank=True,
        help_text="Root Mean Squared Error of ML model on test split."
    )
    model_r2 = models.FloatField(
        null=True,
        blank=True,
        help_text="Coefficient of determination (R²) of ML model on test split."
    )
    model_mbe = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Bias Error of ML model on test split."
    )
    features = models.JSONField(
        default=list,
        help_text="List of input feature names used for model training."
    )
    feature_importances = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature importance mapping from the trained model."
    )
    hyperparameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Model hyperparameters (e.g. n_estimators, max_depth, random_state)."
    )
    artifact_path = models.CharField(
        max_length=512,
        blank=True,
        help_text="Filesystem path where serialized model artifact (.joblib) is saved."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this model is currently the active model for inference."
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional training or research notes."
    )

    class Meta:
        db_table = 'model_metadata'
        ordering = ['-trained_at']
        verbose_name = 'Model Metadata'
        verbose_name_plural = 'Model Metadata'

    def __str__(self):
        return f"{self.version} ({self.target}) — ML MAE: {self.model_mae} vs Baseline: {self.baseline_mae}"
