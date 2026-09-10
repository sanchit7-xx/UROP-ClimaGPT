"""
crops/models.py

Two models:
  GrowthStage  — extensible, database-driven (NOT a static enum)
  CropProfile  — one farm can have many crop records

GrowthStage design rationale:
  Different crops have different lifecycle phases (e.g., wheat has "Tillering"
  and "Boot" stages that rice does not).  Using a DB model instead of a
  TextChoices enum means Stage 2 can add crop-specific stages without
  schema migrations — just insert new rows.

  crop_type=None means the stage is generic (applicable to all crops).
  crop_type='wheat' means the stage is specific to wheat.

  The initial generic set is seeded via:
      python manage.py seed_growth_stages

CropProfile design:
  - Linked to Farm (not directly to FarmerProfile) to support per-farm
    crop tracking even when the same farmer grows different crops on
    different farms.
  - expected_harvest_date is optional (farmer may not know it at sowing time).
  - Validation that harvest > sowing is enforced in the serializer.
"""
from django.db import models

from core.models import TimeStampedModel


# ---------------------------------------------------------------------------
# GrowthStage — extensible, database-driven
# ---------------------------------------------------------------------------

class GrowthStage(models.Model):
    """
    A named growth stage for a crop type.

    Generic stages (crop_type=None):
        Seedling → Vegetative → Flowering → Fruiting → Maturity → Harvest

    Crop-specific stages (Stage 2+):
        crop_type='wheat' → Germination → Tillering → Jointing → Boot →
                            Heading → Grain Fill → Dough → Maturity

    Relationships:
        GrowthStage 1──* CropProfile
    """
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(
        default=0,
        help_text='Display/sort order within a crop type lifecycle.',
    )
    description = models.TextField(
        blank=True,
        help_text='Brief description of what happens during this stage.',
    )
    crop_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Null = generic stage applicable to all crops. '
                  'Set to a crop name (e.g. "wheat") for crop-specific stages.',
    )

    class Meta:
        ordering = ['crop_type', 'order']
        unique_together = [('name', 'crop_type')]
        verbose_name = 'Growth Stage'
        verbose_name_plural = 'Growth Stages'

    def __str__(self):
        if self.crop_type:
            return f'{self.name} ({self.crop_type})'
        return f'{self.name} (generic)'


# ---------------------------------------------------------------------------
# Choices for CropProfile
# ---------------------------------------------------------------------------

class SoilTypeChoices(models.TextChoices):
    CLAY = 'clay', 'Clay'
    SANDY = 'sandy', 'Sandy'
    LOAMY = 'loamy', 'Loamy'
    SILT = 'silt', 'Silt'
    PEAT = 'peat', 'Peat'
    CHALK = 'chalk', 'Chalk'
    BLACK = 'black', 'Black (Regur)'
    ALLUVIAL = 'alluvial', 'Alluvial'
    OTHER = 'other', 'Other'


class CultivationMethodChoices(models.TextChoices):
    CONVENTIONAL = 'conventional', 'Conventional'
    ORGANIC = 'organic', 'Organic'
    HYDROPONIC = 'hydroponic', 'Hydroponic'
    MIXED = 'mixed', 'Mixed'
    ZERO_TILLAGE = 'zero_tillage', 'Zero Tillage'
    OTHER = 'other', 'Other'


# ---------------------------------------------------------------------------
# CropProfile
# ---------------------------------------------------------------------------

class CropProfile(TimeStampedModel):
    """
    A crop record for a specific farm.

    Relationships:
        CropProfile *──1 Farm
        CropProfile *──1 GrowthStage   (nullable — stage may not be known at sowing)

    Stage 2 will add:
        CropProfile 1──* CropRiskAssessment
        CropProfile 1──* IrrigationAdvice
    """
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        related_name='crops',
    )
    crop_name = models.CharField(max_length=100)
    crop_variety = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g., HD 2967 for wheat, Pusa Basmati 1121 for rice.',
    )
    sowing_date = models.DateField()
    expected_harvest_date = models.DateField(
        null=True,
        blank=True,
        help_text='May be left blank at sowing time.',
    )
    growth_stage = models.ForeignKey(
        GrowthStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crops',
    )
    soil_type = models.CharField(
        max_length=20,
        choices=SoilTypeChoices.choices,
        blank=True,
    )
    cultivation_method = models.CharField(
        max_length=20,
        choices=CultivationMethodChoices.choices,
        blank=True,
    )

    class Meta:
        verbose_name = 'Crop Profile'
        verbose_name_plural = 'Crop Profiles'
        ordering = ['-sowing_date']

    def __str__(self):
        return f'{self.crop_name} ({self.farm.farm_name})'
