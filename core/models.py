"""Event audit log model.

Per Part A §2.4, every state-changing operation writes an Event row. The events
table grows fast — see the OPERATIONAL NOTE in Part A about quarterly archival
to compressed JSONL on Backblaze B2.

Tier 2 event types are enumerated in Part B-1 §6.3.
"""
import uuid

from django.db import models


class Event(models.Model):
    """An audit log entry.

    `payload` carries event-specific structured context. `actor_user_id` or
    `actor_respondent_id` should be set (one or the other, occasionally both).
    System events with no human actor leave both NULL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(
        max_length=50,
        help_text='Dotted namespace, e.g. tier_2.respondent_completed',
    )
    actor_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
        db_column='actor_user_id',
    )
    actor_respondent = models.ForeignKey(
        'engagements.Respondent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
        db_column='actor_respondent_id',
    )
    engagement = models.ForeignKey(
        'engagements.Engagement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
        db_column='engagement_id',
    )
    payload = models.JSONField(default=dict)
    # Postgres INET column — we map to CharField for psycopg compatibility.
    # The DB will still enforce INET validation on direct inserts.
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'events'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}'
