"""Initial migration for scoring app — Score model, managed=False."""
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
            name='Score',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('framework', models.CharField(choices=[
                    ('v1_audit', 'AI Business Enablement Audit (V1)'),
                    ('v2_readiness', 'AI Readiness & Performance Assessment (V2)'),
                    ('v3_governance', 'AI Risk & Governance Review (V3)'),
                    ('efficiency', 'AI Efficiency & Process Optimization'),
                ], max_length=50)),
                ('dimension', models.CharField(blank=True, help_text='Sub-dimension name. Null = composite/overall framework score.', max_length=100, null=True)),
                ('score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('maturity_level', models.IntegerField(blank=True, help_text='1-5 per AI Readiness Maturity Scale / AI Governance Maturity Scale', null=True)),
                ('score_components', models.JSONField(blank=True, null=True)),
                ('confidence_level', models.CharField(blank=True, choices=[
                    ('high', "High (≤15% don't know)"),
                    ('medium', "Medium (16-35% don't know)"),
                    ('low', "Low (≥36% don't know)"),
                ], max_length=20, null=True)),
                ('gaps_identified', models.JSONField(default=list)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('engagement', models.ForeignKey(db_column='engagement_id', on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='engagements.engagement')),
            ],
            options={
                'db_table': 'scores',
                'ordering': ['engagement', 'framework', 'dimension'],
                'managed': False,
            },
        ),
    ]
