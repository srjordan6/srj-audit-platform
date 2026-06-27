"""Initial migration for engagements app.

The 'engagements', 'respondents', and 'documents' tables were created by the
srj-mcp PostgreSQL bootstrap. All three models are managed=False so this
migration registers them in Django's migration history without DDL.

Run via: migrate --fake-initial
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Engagement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tier', models.CharField(choices=[
                    ('tier_1', 'Tier 1 — Snapshot'),
                    ('tier_2', 'Tier 2 — Self-Service Audit'),
                    ('tier_3', 'Tier 3 — Consulting Engagement'),
                ], max_length=20)),
                ('status', models.CharField(choices=[
                    ('in_progress', 'In Progress'),
                    ('awaiting_coverage', 'Awaiting Coverage'),
                    ('report_generating', 'Report Generating'),
                    ('completed', 'Completed'),
                    ('expired', 'Expired'),
                    ('refunded', 'Refunded'),
                    ('abandoned', 'Abandoned'),
                    ('extended', 'Extended'),
                ], default='in_progress', max_length=30)),
                ('payment_status', models.CharField(choices=[
                    ('free', 'Free'),
                    ('pending', 'Pending'),
                    ('paid', 'Paid'),
                    ('refunded', 'Refunded'),
                    ('failed', 'Failed'),
                ], default='free', max_length=30)),
                ('stripe_payment_intent_id', models.CharField(blank=True, max_length=255, null=True)),
                ('stripe_identity_session_id', models.CharField(blank=True, max_length=255, null=True)),
                ('identity_verification_status', models.CharField(choices=[
                    ('not_required', 'Not Required'),
                    ('pending', 'Pending'),
                    ('verified', 'Verified'),
                    ('failed', 'Failed'),
                ], default='not_required', max_length=30)),
                ('price_cents', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('buyer_attestation_signed_at', models.DateTimeField(blank=True, null=True)),
                ('buyer_attestation_text', models.TextField(blank=True, null=True)),
                ('buyer_attestation_name', models.CharField(blank=True, max_length=255, null=True)),
                ('extension_count', models.IntegerField(default=0)),
                ('coverage_met_at', models.DateTimeField(blank=True, null=True)),
                ('buyer_user', models.ForeignKey(db_column='buyer_user_id', on_delete=django.db.models.deletion.PROTECT, related_name='purchased_engagements', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.PROTECT, related_name='engagements', to='accounts.company')),
            ],
            options={
                'db_table': 'engagements',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Respondent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=255)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('role', models.CharField(max_length=100)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('invitation_token', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('invitation_sent_at', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('attestation_signed_at', models.DateTimeField(blank=True, null=True)),
                ('attestation_text', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[
                    ('invited', 'Invited'),
                    ('started', 'Started'),
                    ('completed', 'Completed'),
                    ('removed', 'Removed'),
                    ('expired', 'Expired'),
                ], default='invited', max_length=30)),
                ('completion_percentage', models.DecimalField(decimal_places=2, default=0.0, help_text="Percent of assigned questions answered. 60.00 is the threshold for counting toward sample size.", max_digits=5)),
                ('last_activity_at', models.DateTimeField(blank=True, null=True)),
                ('buyer_personal_note', models.TextField(blank=True, null=True)),
                ('reminder_count', models.IntegerField(default=0)),
                ('engagement', models.ForeignKey(db_column='engagement_id', on_delete=django.db.models.deletion.CASCADE, related_name='respondents', to='engagements.engagement')),
                ('user', models.ForeignKey(blank=True, db_column='user_id', help_text='NULL for invited respondents who do not have a User account.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='respondent_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'respondents',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file_path', models.CharField(max_length=500)),
                ('original_filename', models.CharField(max_length=255)),
                ('file_size_bytes', models.BigIntegerField()),
                ('mime_type', models.CharField(blank=True, max_length=100, null=True)),
                ('document_category', models.CharField(blank=True, choices=[
                    ('ai_usage_policy', 'AI Usage Policy'),
                    ('tool_inventory', 'AI Tool Inventory'),
                    ('vendor_contract', 'Vendor Contract'),
                    ('board_materials', 'Board Materials'),
                    ('insurance', 'Insurance Policy'),
                    ('supplementary', 'Supplementary'),
                ], max_length=50, null=True)),
                ('scan_status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('clean', 'Clean'),
                    ('rejected', 'Rejected'),
                ], default='pending', max_length=30)),
                ('extracted_text', models.TextField(blank=True, null=True)),
                ('extraction_status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('not_applicable', 'Not Applicable'),
                ], default='pending', max_length=30)),
                ('srj_reviewer_notes', models.TextField(blank=True, null=True)),
                ('srj_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('engagement', models.ForeignKey(db_column='engagement_id', on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='engagements.engagement')),
                ('srj_reviewed_by_user', models.ForeignKey(blank=True, db_column='srj_reviewed_by_user_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_documents', to=settings.AUTH_USER_MODEL)),
                ('uploaded_by_user', models.ForeignKey(db_column='uploaded_by_user_id', on_delete=django.db.models.deletion.PROTECT, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'documents',
                'ordering': ['-uploaded_at'],
                'managed': False,
            },
        ),
    ]
