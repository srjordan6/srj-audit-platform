"""Initial migration for questionnaire app.

The 'questions' and 'responses' tables were created by the srj-mcp bootstrap.
The questions table also has scoring_overrides and extended_metadata JSONB
columns added via the v1.2 patch (2026-06-23).

Both models are managed=False — migrate --fake-initial registers them without DDL.
"""
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
            name='Question',
            fields=[
                ('id', models.CharField(help_text='e.g. T1-A-001', max_length=20, primary_key=True, serialize=False)),
                ('tier', models.CharField(choices=[
                    ('tier_1', 'Tier 1'),
                    ('tier_2', 'Tier 2'),
                    ('tier_3', 'Tier 3'),
                ], max_length=20)),
                ('section', models.CharField(max_length=50)),
                ('subsection', models.CharField(blank=True, max_length=100, null=True)),
                ('sequence_number', models.IntegerField()),
                ('question_text', models.TextField()),
                ('question_type', models.CharField(choices=[
                    ('SS', 'Single Select'),
                    ('MS', 'Multi-Select'),
                    ('YN', "Yes / No / Don't Know"),
                    ('NR', 'Numeric Range'),
                    ('RANK', 'Ranked Order'),
                    ('L5', 'Likert 1-5'),
                    ('MATRIX', 'Matrix'),
                    ('TEXT', 'Free Text'),
                ], max_length=30)),
                ('options', models.JSONField(blank=True, help_text='Array of option labels for select types', null=True)),
                ('matrix_rows', models.JSONField(blank=True, null=True)),
                ('matrix_columns', models.JSONField(blank=True, null=True)),
                ('skip_logic', models.JSONField(blank=True, null=True)),
                ('role_visibility', models.JSONField(default=list, help_text='List of roles. ["all"] for universal.')),
                ('required', models.BooleanField(default=True)),
                ('scoring_weight', models.DecimalField(decimal_places=2, default=1.0, max_digits=5)),
                ('framework_mappings', models.JSONField(default=list)),
                ('notes', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('scoring_overrides', models.JSONField(blank=True, null=True)),
                ('extended_metadata', models.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'questions',
                'ordering': ['tier', 'section', 'sequence_number'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Response',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('answer_value', models.JSONField()),
                ('is_dont_know', models.BooleanField(default=False)),
                ('answered_at', models.DateTimeField(auto_now_add=True)),
                ('question', models.ForeignKey(db_column='question_id', on_delete=django.db.models.deletion.PROTECT, related_name='responses', to='questionnaire.question')),
                ('respondent', models.ForeignKey(db_column='respondent_id', on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='engagements.respondent')),
            ],
            options={
                'db_table': 'responses',
                'ordering': ['-answered_at'],
                'unique_together': {('respondent', 'question')},
                'managed': False,
            },
        ),
    ]
