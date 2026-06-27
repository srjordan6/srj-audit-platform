"""Question and Response models.

Question is keyed by string ID (e.g. 'T1-A-001') because question IDs are
human-readable and stable across schema changes. Response is keyed by UUID and
unique per (respondent, question).

Both models are managed=False — tables created by srj-mcp bootstrap. The
`questions` table includes the scoring_overrides and extended_metadata JSONB
columns added 2026-06-23 per the v1.2 patch spec.
"""
import uuid

from django.db import models


class Question(models.Model):
    """A single question in the canonical question bank.

    The bank is loaded from JSON manifests (see questionnaire/question_bank.py
    in a future commit) via a management command.
    """

    TIER_CHOICES = [
        ('tier_1', 'Tier 1'),
        ('tier_2', 'Tier 2'),
        ('tier_3', 'Tier 3'),
    ]

    QUESTION_TYPE_CHOICES = [
        ('SS', 'Single Select'),
        ('MS', 'Multi-Select'),
        ('YN', 'Yes / No / Don\'t Know'),
        ('NR', 'Numeric Range'),
        ('RANK', 'Ranked Order'),
        ('L5', 'Likert 1-5'),
        ('MATRIX', 'Matrix'),
        ('TEXT', 'Free Text'),
    ]

    id = models.CharField(max_length=20, primary_key=True, help_text='e.g. T1-A-001')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    section = models.CharField(max_length=50)
    subsection = models.CharField(max_length=100, blank=True, null=True)
    sequence_number = models.IntegerField()
    question_text = models.TextField()
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES)
    options = models.JSONField(blank=True, null=True, help_text='Array of option labels for select types')
    matrix_rows = models.JSONField(blank=True, null=True)
    matrix_columns = models.JSONField(blank=True, null=True)
    skip_logic = models.JSONField(blank=True, null=True)
    role_visibility = models.JSONField(default=list, help_text='List of roles. ["all"] for universal.')
    required = models.BooleanField(default=True)
    scoring_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    framework_mappings = models.JSONField(default=list)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    # v1.2 patch additions (per memory note + scoring_overrides for OD-12)
    scoring_overrides = models.JSONField(blank=True, null=True)
    extended_metadata = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = 'questions'
        managed = False
        ordering = ['tier', 'section', 'sequence_number']

    def __str__(self):
        return f'{self.id}: {self.question_text[:60]}...'

    def is_visible_for_role(self, role: str) -> bool:
        """Return True if a respondent of the given role should see this question."""
        if not self.role_visibility:
            return True
        return 'all' in self.role_visibility or role in self.role_visibility


class Response(models.Model):
    """A single answer to a single question from a single respondent.

    The answer_value JSONB structure depends on question_type — see Part A §2.4
    for the canonical shapes (single_select, multi_select, numeric_range,
    rank_order, matrix).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    respondent = models.ForeignKey(
        'engagements.Respondent',
        on_delete=models.CASCADE,
        related_name='responses',
        db_column='respondent_id',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name='responses',
        db_column='question_id',
    )
    answer_value = models.JSONField()
    is_dont_know = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'responses'
        managed = False
        unique_together = [('respondent', 'question')]
        ordering = ['-answered_at']

    def __str__(self):
        return f'{self.respondent.email if self.respondent_id else "?"} → {self.question_id}'
