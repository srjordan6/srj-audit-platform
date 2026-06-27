"""Score model — calculated scoring outputs per engagement.

One Score row per (engagement, framework, dimension) combination. The scoring
engine writes these rows after a coverage check passes; the report generator
reads them. Both are background jobs (RQ).
"""
import uuid

from django.db import models


class Score(models.Model):
    """A calculated score for one dimension of one framework on one engagement."""

    FRAMEWORK_CHOICES = [
        ('v1_audit', 'AI Business Enablement Audit (V1)'),
        ('v2_readiness', 'AI Readiness & Performance Assessment (V2)'),
        ('v3_governance', 'AI Risk & Governance Review (V3)'),
        ('efficiency', 'AI Efficiency & Process Optimization'),
    ]

    CONFIDENCE_CHOICES = [
        ('high', 'High (≤15% don\'t know)'),
        ('medium', 'Medium (16-35% don\'t know)'),
        ('low', 'Low (≥36% don\'t know)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.CASCADE,
        related_name='scores',
        db_column='engagement_id',
    )
    framework = models.CharField(max_length=50, choices=FRAMEWORK_CHOICES)
    dimension = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Sub-dimension name. Null = composite/overall framework score.',
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    maturity_level = models.IntegerField(
        null=True, blank=True,
        help_text='1-5 per AI Readiness Maturity Scale / AI Governance Maturity Scale',
    )
    score_components = models.JSONField(blank=True, null=True)
    confidence_level = models.CharField(
        max_length=20, choices=CONFIDENCE_CHOICES, blank=True, null=True
    )
    gaps_identified = models.JSONField(default=list)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scores'
        managed = False
        ordering = ['engagement', 'framework', 'dimension']

    def __str__(self):
        dim = self.dimension or 'composite'
        return f'{self.framework}.{dim} = {self.score} ({self.confidence_level})'
