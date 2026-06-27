"""Admin registration for reports app."""
from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'engagement', 'framework', 'report_type',
        'delivered_at', 'download_count', 'generated_at',
    )
    list_filter = ('framework', 'report_type', 'generated_at', 'delivered_at')
    search_fields = ('engagement__id', 'engagement__company__name', 'delivered_to_email')
    readonly_fields = (
        'id', 'generated_at', 'delivered_at',
        'download_count', 'last_downloaded_at', 'file_size_bytes',
    )
    raw_id_fields = ('engagement',)
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'engagement', 'framework', 'report_type'),
        }),
        ('File', {
            'fields': ('file_path', 'file_size_bytes', 'generated_at'),
        }),
        ('Delivery', {
            'fields': ('delivered_to_email', 'delivered_at'),
        }),
        ('Download metrics', {
            'fields': ('download_count', 'last_downloaded_at'),
            'classes': ('collapse',),
        }),
    )
    ordering = ('-generated_at',)
