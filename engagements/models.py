"""Engagement, Respondent, and Document models.

All three are managed=False — underlying tables were created by the srj-mcp
PostgreSQL bootstrap. Schemas mirror Part A v1.1 §2.4 and Part B-1 §9.
"""
import uuid

from django.db import models


class Engagement(models.Model):
    """Tier 1, 2, or 3 audit engagement.

    One per purchase (or attempted purchase). Lifecycle states are documented
    in Part B-1 §1.3.
    """

    TIER_CHOICES = [
        ('tier_1', 'Tier 1 — Snapshot'),
        ('tier_2', 'Tier 2 — Self-Service Audit'),
        ('tier_3', 'Tier 3 — Consulting Engagement'),
    ]

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('awaiting_coverage', 'Awaiting Coverage'),
        ('report_generating', 'Report Generating'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('refunded', 'Refunded'),
        ('abandoned', 'Abandoned'),
        ('extended', 'Extended'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('free', 'Free'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
        ('comped', 'Comped (promo/tester code)'),
    ]

    IDENTITY_STATUS_CHOICES = [
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.PROTECT,
        related_name='engagements',
        db_column='company_id',
    )
    buyer_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='purchased_engagements',
        db_column='buyer_user_id',
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='in_progress')
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='free')
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_identity_session_id = models.CharField(max_length=255, blank=True, null=True)
    identity_verification_status = models.CharField(
        max_length=30, choices=IDENTITY_STATUS_CHOICES, default='not_required'
    )
    price_cents = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Part B-1 §9 additions
    buyer_attestation_signed_at = models.DateTimeField(null=True, blank=True)
    buyer_attestation_text = models.TextField(blank=True, null=True)
    buyer_attestation_name = models.CharField(max_length=255, blank=True, null=True)
    extension_count = models.IntegerField(default=0)
    coverage_met_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'engagements'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tier} — {self.company.name if self.company_id else "?"} ({self.status})'

    @property
    def price_dollars(self):
        return self.price_cents / 100 if self.price_cents else 0


class Respondent(models.Model):
    """Person answering questions on behalf of a company in an engagement.

    For Tier 1, exactly one respondent per engagement (the buyer). For Tier 2/3,
    typically multiple invited respondents. Authenticated via magic-link token
    rather than a User account (see Part B-1 §4).
    """

    STATUS_CHOICES = [
        ('invited', 'Invited'),
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('removed', 'Removed'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(
        Engagement,
        on_delete=models.CASCADE,
        related_name='respondents',
        db_column='engagement_id',
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respondent_records',
        db_column='user_id',
        help_text='NULL for invited respondents who do not have a User account.',
    )
    email = models.EmailField(max_length=255)
    name = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=100)
    title = models.CharField(max_length=255, blank=True, null=True)
    invitation_token = models.CharField(max_length=255, unique=True, blank=True, null=True)
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attestation_signed_at = models.DateTimeField(null=True, blank=True)
    attestation_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Part B-1 §9 additions
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='invited')
    completion_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text='Percent of assigned questions answered. 60.00 is the threshold for counting toward sample size.',
    )
    last_activity_at = models.DateTimeField(null=True, blank=True)
    buyer_personal_note = models.TextField(blank=True, null=True)
    reminder_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'respondents'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.role}) — {self.status}'


class Document(models.Model):
    """Supporting document uploaded by buyer for Tier 2/3 engagements (Part B-1 §5)."""

    CATEGORY_CHOICES = [
        ('ai_usage_policy', 'AI Usage Policy'),
        ('tool_inventory', 'AI Tool Inventory'),
        ('vendor_contract', 'Vendor Contract'),
        ('board_materials', 'Board Materials'),
        ('insurance', 'Insurance Policy'),
        ('supplementary', 'Supplementary'),
    ]

    SCAN_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('clean', 'Clean'),
        ('rejected', 'Rejected'),
    ]

    EXTRACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('not_applicable', 'Not Applicable'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(
        Engagement,
        on_delete=models.CASCADE,
        related_name='documents',
        db_column='engagement_id',
    )
    uploaded_by_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='uploaded_documents',
        db_column='uploaded_by_user_id',
    )
    file_path = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    document_category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True
    )
    scan_status = models.CharField(max_length=30, choices=SCAN_STATUS_CHOICES, default='pending')
    extracted_text = models.TextField(blank=True, null=True)
    extraction_status = models.CharField(
        max_length=30, choices=EXTRACTION_STATUS_CHOICES, default='pending'
    )
    srj_reviewer_notes = models.TextField(blank=True, null=True)
    srj_reviewed_at = models.DateTimeField(null=True, blank=True)
    srj_reviewed_by_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
        db_column='srj_reviewed_by_user_id',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'documents'
        managed = False
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.original_filename} ({self.document_category})'

    @property
    def is_deleted(self):
        return self.deleted_at is not None
