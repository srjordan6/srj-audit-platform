"""Admin registration for engagements app."""
from django.contrib import admin

from .models import Document, Engagement, Respondent


class RespondentInline(admin.TabularInline):
    model = Respondent
    extra = 0
    fields = ('email', 'name', 'role', 'status', 'completion_percentage', 'completed_at')
    readonly_fields = ('completed_at',)
    show_change_link = True


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    fields = ('original_filename', 'document_category', 'scan_status', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    show_change_link = True


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'tier', 'company', 'buyer_user', 'status',
        'payment_status', 'price_dollars', 'created_at',
    )
    list_filter = ('tier', 'status', 'payment_status', 'identity_verification_status', 'created_at')
    search_fields = ('id', 'company__name', 'buyer_user__email', 'stripe_payment_intent_id')
    readonly_fields = ('id', 'created_at', 'completed_at', 'coverage_met_at')
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'tier', 'company', 'buyer_user'),
        }),
        ('Status & lifecycle', {
            'fields': ('status', 'created_at', 'completed_at', 'expires_at', 'coverage_met_at', 'extension_count'),
        }),
        ('Payment', {
            'fields': (
                'payment_status', 'price_cents',
                'stripe_payment_intent_id', 'identity_verification_status',
                'stripe_identity_session_id',
            ),
        }),
        ('Buyer attestation (Tier 2/3)', {
            'fields': ('buyer_attestation_signed_at', 'buyer_attestation_name', 'buyer_attestation_text'),
            'classes': ('collapse',),
        }),
    )
    inlines = [RespondentInline, DocumentInline]
    ordering = ('-created_at',)


@admin.register(Respondent)
class RespondentAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'role', 'engagement', 'status',
        'completion_percentage', 'completed_at',
    )
    list_filter = ('status', 'role', 'engagement__tier', 'completed_at')
    search_fields = ('email', 'name', 'invitation_token', 'engagement__company__name')
    readonly_fields = ('id', 'created_at', 'invitation_sent_at', 'started_at', 'completed_at', 'attestation_signed_at')
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'engagement', 'user', 'email', 'name', 'role', 'title'),
        }),
        ('Invitation & progress', {
            'fields': (
                'invitation_token', 'invitation_sent_at', 'reminder_count',
                'status', 'started_at', 'last_activity_at', 'completion_percentage', 'completed_at',
            ),
        }),
        ('Attestation', {
            'fields': ('attestation_signed_at', 'attestation_text'),
            'classes': ('collapse',),
        }),
        ('Buyer note', {
            'fields': ('buyer_personal_note',),
            'classes': ('collapse',),
        }),
    )
    ordering = ('-created_at',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename', 'document_category', 'engagement',
        'scan_status', 'extraction_status', 'uploaded_at',
    )
    list_filter = ('document_category', 'scan_status', 'extraction_status', 'uploaded_at')
    search_fields = ('original_filename', 'engagement__company__name', 'srj_reviewer_notes')
    readonly_fields = ('id', 'uploaded_at', 'srj_reviewed_at', 'file_size_bytes')
    fieldsets = (
        ('File', {
            'fields': ('id', 'original_filename', 'file_path', 'file_size_bytes', 'mime_type', 'document_category'),
        }),
        ('Engagement & uploader', {
            'fields': ('engagement', 'uploaded_by_user', 'uploaded_at'),
        }),
        ('Processing', {
            'fields': ('scan_status', 'extraction_status', 'extracted_text'),
        }),
        ('SRJ review', {
            'fields': ('srj_reviewed_by_user', 'srj_reviewed_at', 'srj_reviewer_notes'),
        }),
        ('Deletion', {
            'fields': ('deleted_at',),
            'classes': ('collapse',),
        }),
    )
    ordering = ('-uploaded_at',)
