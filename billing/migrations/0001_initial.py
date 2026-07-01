"""Initial migration for billing app — DiscountCredit + RefundRequest, managed=False."""
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
            name='DiscountCredit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('credit_type', models.CharField(choices=[
                    ('tier_1_upgrade', 'Tier 1 → Tier 2 Upgrade Credit ($399)'),
                    ('nurture_15pct', 'Nurture Sequence 15% Discount'),
                    ('manual', 'Manual / Goodwill Credit'),
                ], max_length=50)),
                ('amount_cents', models.IntegerField(help_text='Fixed-amount credit (cents). May be 0 for percent-only credits.')),
                ('percentage', models.DecimalField(blank=True, decimal_places=2, help_text='Percent discount, e.g. 15.00 for 15%. NULL for fixed-amount credits.', max_digits=5, null=True)),
                ('expires_at', models.DateTimeField()),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('applied_to_engagement', models.ForeignKey(blank=True, db_column='applied_to_engagement_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_credits', to='engagements.engagement')),
                ('source_engagement', models.ForeignKey(blank=True, db_column='source_engagement_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_credits', to='engagements.engagement')),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='discount_credits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'discount_credits',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='RefundRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('approved_full', 'Approved (Full)'),
                    ('approved_partial', 'Approved (Partial)'),
                    ('denied', 'Denied'),
                ], default='pending', max_length=30)),
                ('approved_amount_cents', models.IntegerField(blank=True, null=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('stripe_refund_id', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_by_user', models.ForeignKey(blank=True, db_column='decided_by_user_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='refund_decisions', to=settings.AUTH_USER_MODEL)),
                ('engagement', models.ForeignKey(db_column='engagement_id', on_delete=django.db.models.deletion.PROTECT, related_name='refund_requests', to='engagements.engagement')),
                ('requested_by_user', models.ForeignKey(db_column='requested_by_user_id', on_delete=django.db.models.deletion.PROTECT, related_name='refund_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'refund_requests',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
    ]
