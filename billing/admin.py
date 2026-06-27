"""Admin registration for billing app."""
from django.contrib import admin

from .models import DiscountCredit, RefundRequest


@admin.register(DiscountCredit)
class DiscountCreditAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'credit_type', 'amount_cents', 'percentage',
        'expires_at', 'is_applied', 'created_at',
    )
    list_filter = ('credit_type', 'expires_at', 'created_at')
    search_fields = ('user__email', 'source_engagement__id', 'applied_to_engagement__id')
    readonly_fields = ('id', 'created_at', 'applied_at', 'is_applied', 'is_expired')
    raw_id_fields = ('source_engagement', 'applied_to_engagement', 'user')
    fieldsets = (
        ('Credit', {
            'fields': ('id', 'user', 'credit_type', 'amount_cents', 'percentage'),
        }),
        ('Validity', {
            'fields': ('expires_at', 'is_expired', 'created_at'),
        }),
        ('Source & application', {
            'fields': ('source_engagement', 'applied_to_engagement', 'applied_at', 'is_applied'),
        }),
    )
    ordering = ('-created_at',)


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'requested_by_user', 'status', 'approved_amount_cents', 'created_at', 'decided_at')
    list_filter = ('status', 'created_at', 'decided_at')
    search_fields = ('engagement__id', 'requested_by_user__email', 'stripe_refund_id', 'reason')
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('engagement', 'requested_by_user', 'decided_by_user')
    fieldsets = (
        ('Request', {
            'fields': ('id', 'engagement', 'requested_by_user', 'reason', 'created_at'),
        }),
        ('Decision', {
            'fields': ('status', 'approved_amount_cents', 'decided_by_user', 'decided_at'),
        }),
        ('Stripe', {
            'fields': ('stripe_refund_id',),
        }),
    )
    ordering = ('-created_at',)
