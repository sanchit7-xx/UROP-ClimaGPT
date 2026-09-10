"""accounts/admin.py"""
from django.contrib import admin

from .models import FarmerProfile


@admin.register(FarmerProfile)
class FarmerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'user', 'phone_number',
        'preferred_language', 'state', 'district', 'created_at',
    ]
    search_fields = ['full_name', 'user__email', 'phone_number', 'state']
    list_filter = ['preferred_language', 'gender', 'state']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
