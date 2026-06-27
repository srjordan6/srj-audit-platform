"""Admin registration for scoring app."""
from django.contrib import admin

from .models import Score


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'framework', 'dimension', 'score', 'maturity_level', 'confidence_level', 'calculated_at')
    list_filter = ('framework', 'confidence_level', 'maturity_level', 'calculated_at')
    search_fields = ('engagement__id', 'engagement__company__name', 'dimension')
    readonly_fields = ('id', 'calculated_at', 'score_components', 'gaps_identified')
    raw_id_fields = ('engagement',)
    ordering = ('-calculated_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Read-only; scoring engine writes these.
        return False
