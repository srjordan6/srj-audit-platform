"""Mirror the hand-applied `report_id` column on scores (managed=False).

The table is hand-managed; the SQL lives at
C:\\srj-data\\sql\\2026-09-05_scores_report_id.sql and must be applied by
the table owner. This migration only keeps Django's model state in sync so
future autodetector runs stay quiet.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scoring', '0001_initial'),
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='score',
            name='report',
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column='report_id',
                help_text=(
                    'The report of record these scores were computed for. '
                    'Rows are appended per generation, never overwritten, so '
                    'this is what makes the table a trend source rather than '
                    'a cache.'
                ),
                on_delete=django.db.models.deletion.CASCADE,
                related_name='scores',
                to='reports.report',
            ),
        ),
    ]
