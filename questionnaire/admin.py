"""Admin registration for questionnaire app."""
from django.contrib import admin

from .models import Question, Response


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'tier', 'section', 'sequence_number', 'question_type', 'required', 'is_active')
    list_filter = ('tier', 'section', 'question_type', 'required', 'is_active')
    search_fields = ('id', 'question_text', 'notes')
    readonly_fields = ('id',)
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'tier', 'section', 'subsection', 'sequence_number'),
        }),
        ('Content', {
            'fields': ('question_text', 'question_type', 'required'),
        }),
        ('Answer shape', {
            'fields': ('options', 'matrix_rows', 'matrix_columns'),
            'classes': ('collapse',),
        }),
        ('Visibility & flow', {
            'fields': ('role_visibility', 'skip_logic', 'is_active'),
        }),
        ('Scoring', {
            'fields': ('scoring_weight', 'framework_mappings', 'scoring_overrides'),
        }),
        ('Metadata', {
            'fields': ('notes', 'extended_metadata'),
            'classes': ('collapse',),
        }),
    )
    ordering = ('tier', 'section', 'sequence_number')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('respondent', 'question', 'is_dont_know', 'answered_at')
    list_filter = ('is_dont_know', 'question__tier', 'question__section', 'answered_at')
    search_fields = ('respondent__email', 'question__id')
    readonly_fields = ('id', 'answered_at')
    raw_id_fields = ('respondent',)
    ordering = ('-answered_at',)

    def has_add_permission(self, request):
        # Responses are created by the questionnaire flow controller, not the admin.
        return False
