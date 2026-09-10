"""farms/admin.py"""
from django.contrib import admin

from .models import Farm


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = [
        'farm_name', 'farmer', 'farm_area', 'farm_area_unit',
        'irrigation_type', 'district', 'state', 'created_at',
    ]
    search_fields = [
        'farm_name', 'farmer__full_name', 'farmer__user__email',
        'district', 'state',
    ]
    list_filter = ['irrigation_type', 'farm_area_unit', 'state']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = [
        ('Basic Information', {
            'fields': ('farmer', 'farm_name', 'farm_area', 'farm_area_unit', 'irrigation_type'),
        }),
        ('Primary Location (GPS)', {
            'fields': ('latitude', 'longitude'),
            'description': 'Canonical location — used for all weather/risk calculations.',
        }),
        ('Supplementary Address (from Mapbox)', {
            'fields': ('village', 'locality', 'city', 'district', 'state', 'country', 'postal_code'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    ]
