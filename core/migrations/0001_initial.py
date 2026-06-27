"""Initial migration for core app — Event audit log, managed=False."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('engagements', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(help_text='Dotted namespace, e.g. tier_2.respondent_completed', max_length=50)),
                ('payload', models.JSONField(default=dict)),
                ('ip_address', models.CharField(blank=True, max_length=45, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor_respondent', models.ForeignKey(blank=True, db_column='actor_respondent_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to='engagements.respondent')),
                ('actor_user', models.ForeignKey(blank=True, db_column='actor_user_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to=settings.AUTH_USER_MODEL)),
                ('engagement', models.ForeignKey(blank=True, db_column='engagement_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to='engagements.engagement')),
            ],
            options={
                'db_table': 'events',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
    ]
