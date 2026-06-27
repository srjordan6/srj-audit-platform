"""Billing-related models: discount credits and refund requests.

Both per Part B-1 §9. Used by the Stripe checkout flow (DiscountCredit) and the
manual refund review workflow (RefundRequest).
"""
import uuid

from django.db import models


class DiscountCredit(models.Model):
    """A credit applied to a user's account, valid for one engagement purchase.

    Two primary sources:
    - Tier 1 → Tier 2 upgrade: $199 credit, 90-day validity (Decision B-5)
    - Nurture sequence: 15% off Tier 2, 14-day validity (Decision 7-7)

    Credits can stack — both may apply to the same purchase.
    """

    CREDIT_TYPE_CHOICES = [
        ('tier_1_upgrade', 'Tier 1 → Tier 2 Upgrade Credit ($199)'),
        ('nurture_15pct', 'Nurture Sequence 15% Discount'),
        ('manual', 'Manual / Goodwill Credit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='discount_credits',
        db_column='user_id',
    )
    source_engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_credits',
        db_column='source_engagement_id',
    )
    credit_type = models.CharField(max_length=50, choices=CREDIT_TYPE_CHOICES)
    amount_cents = models.IntegerField(help_text='Fixed-amount credit (cents). May be 0 for percent-only credits.')
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Percent discount, e.g. 15.00 for 15%. NULL for fixed-amount credits.',
    )
    expires_at = models.DateTimeField()
    applied_to_engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_credits',
        db_column='applied_to_engagement_id',
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discount_credits'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.credit_type} (${self.amount_cents / 100:.2f}) for {self.user.email}'

    @property
    def is_applied(self):
        return self.applied_at is not None

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at < timezone.now()


class RefundRequest(models.Model):
    """A buyer-initiated or SRJ-initiated refund request against an engagement.

    Workflow per Part B-1 §2.3:
    - <24h, no respondents invited: 100% auto
    - <7d, <2 respondents completed: 100% auto
    - >7d, ≥2 respondents completed: 50% manual SRJ review
    - Coverage not reached after 60d: 100% auto
    - Coverage reached, report delivered: no refund
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved_full', 'Approved (Full)'),
        ('approved_partial', 'Approved (Partial)'),
        ('denied', 'Denied'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.PROTECT,
        related_name='refund_requests',
        db_column='engagement_id',
    )
    requested_by_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='refund_requests',
        db_column='requested_by_user_id',
    )
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    approved_amount_cents = models.IntegerField(null=True, blank=True)
    decided_by_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_decisions',
        db_column='decided_by_user_id',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    stripe_refund_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'refund_requests'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund {self.status} for {self.engagement_id}'
