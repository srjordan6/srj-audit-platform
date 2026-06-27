"""Initial migration for reports app — Report model, managed=False."""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('engagements', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('framework', models.CharField(choices=[
                    ('v1_audit', 'V1 Audit'),
                    ('v2_readiness', 'V2 Readiness'),
                    ('v3_governance', 'V3 Governance'),
                    ('efficiency', 'Efficiency'),
                    ('composite', 'Composite'),
                ], max_length=50)),
                ('report_type', models.CharField(choices=[
                    ('snapshot', 'Snapshot (Tier 1)'),
                    ('audit', 'Audit (Tier 2)'),
                    ('engagement', 'Engagement (Tier 3)'),
                ], max_length=30)),
                ('file_path', models.CharField(blank=True, help_text='B2 path', max_length=500, null=True)),
                ('file_size_bytes', models.IntegerField(blank=True, null=True)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('delivered_to_email', models.EmailField(blank=True, max_length=255, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('download_count', models.IntegerField(default=0)),
                ('last_downloaded_at', models.DateTimeField(blank=True, null=True)),
                ('engagement', models.ForeignKey(db_column='engagement_id', on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='engagements.engagement')),
            ],
            options={
                'db_table': 'reports',
                'ordering': ['-generated_at'],
                'managed': False,
            },
        ),
    ]
