"""Admin registration for core app — Event audit log (read-only)."""
from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'engagement', 'actor_user', 'actor_respondent', 'ip_address', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('event_type', 'engagement__id', 'actor_user__email', 'ip_address')
    readonly_fields = (
        'id', 'event_type', 'actor_user', 'actor_respondent',
        'engagement', 'payload', 'ip_address', 'user_agent', 'created_at',
    )
    raw_id_fields = ('actor_user', 'actor_respondent', 'engagement')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Audit log is immutable. View only.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
