"""
accounts/models.py

FarmerProfile — extended profile linked 1-to-1 with Django's built-in User.

Design decisions:
  - Passwords are managed entirely by Django's User model (PBKDF2/Argon2).
    We NEVER store or manipulate passwords manually.
  - Location fields (state/district/village) here represent the farmer's
    HOME location, not the farm location.  Farm locations live in farms.Farm.
  - phone_number is unique across all farmers.
"""
from django.contrib.auth.models import User
from django.db import models

from core.models import TimeStampedModel


class GenderChoices(models.TextChoices):
    MALE = 'M', 'Male'
    FEMALE = 'F', 'Female'
    OTHER = 'O', 'Other'
    PREFER_NOT_TO_SAY = 'N', 'Prefer not to say'


class FarmerProfile(TimeStampedModel):
    """
    Extended profile for a registered farmer.

    Relationships:
        FarmerProfile 1──1 User   (Django auth)
        FarmerProfile 1──* Farm   (via farms.Farm.farmer FK)
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='farmer_profile',
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    preferred_language = models.CharField(max_length=50, default='English')

    # Home location (supplementary; farm-specific location is in farms.Farm)
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)

    # Optional personal details
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=1,
        choices=GenderChoices.choices,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Farmer Profile'
        verbose_name_plural = 'Farmer Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.user.email})'
