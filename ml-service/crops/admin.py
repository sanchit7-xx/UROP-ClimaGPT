"""crops/admin.py"""
from django.contrib import admin

from .models import CropProfile, GrowthStage


@admin.register(GrowthStage)
class GrowthStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'crop_type', 'description']
    list_filter = ['crop_type']
    search_fields = ['name', 'crop_type']
    ordering = ['crop_type', 'order']


@admin.register(CropProfile)
class CropProfileAdmin(admin.ModelAdmin):
    list_display = [
        'crop_name', 'crop_variety', 'farm', 'growth_stage',
        'sowing_date', 'expected_harvest_date', 'soil_type',
    ]
    search_fields = ['crop_name', 'farm__farm_name', 'farm__farmer__full_name']
    list_filter = ['soil_type', 'cultivation_method', 'growth_stage']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-sowing_date']

    fieldsets = [
        ('Crop Information', {
            'fields': ('farm', 'crop_name', 'crop_variety', 'growth_stage'),
        }),
        ('Dates', {
            'fields': ('sowing_date', 'expected_harvest_date'),
        }),
        ('Agronomy', {
            'fields': ('soil_type', 'cultivation_method'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    ]
