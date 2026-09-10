"""
core/models.py

Abstract base models shared across all ClimaGPT apps.
"""
from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that automatically tracks creation and update times.

    All ClimaGPT models should inherit from this class instead of
    models.Model directly, so that audit timestamps are consistently
    available everywhere.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
