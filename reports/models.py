"""Report model — generated PDF deliverables stored to Backblaze B2."""
import uuid

from django.db import models


class Report(models.Model):
    """A generated PDF report for one framework of one engagement.

    A Tier 1 engagement that pays for the $399 report produces 4 Report rows
    (one per framework). Tier 2 produces 4 board-grade reports. Tier 3 produces
    additional engagement-specific deliverables.
    """

    FRAMEWORK_CHOICES = [
        ('v1_audit', 'V1 Audit'),
        ('v2_readiness', 'V2 Readiness'),
        ('v3_governance', 'V3 Governance'),
        ('efficiency', 'Efficiency'),
        ('composite', 'Composite'),
    ]

    REPORT_TYPE_CHOICES = [
        ('snapshot', 'Snapshot (Tier 1)'),
        ('audit', 'Audit (Tier 2)'),
        ('engagement', 'Engagement (Tier 3)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.CASCADE,
        related_name='reports',
        db_column='engagement_id',
    )
    framework = models.CharField(max_length=50, choices=FRAMEWORK_CHOICES)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    file_path = models.CharField(max_length=500, blank=True, null=True, help_text='B2 path')
    file_size_bytes = models.IntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    delivered_to_email = models.EmailField(max_length=255, blank=True, null=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reports'
        managed = False
        ordering = ['-generated_at']

    def __str__(self):
        return f'{self.framework} {self.report_type} ({self.engagement_id})'
