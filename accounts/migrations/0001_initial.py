"""Initial migration for accounts app.

The 'companies' and 'users' tables were created by the srj-mcp PostgreSQL
bootstrap on 2026-06-23. Both models declare Meta.managed=False so Django
does not attempt to re-create them. This migration registers the models in
Django's migration history so that AUTH_USER_MODEL = 'accounts.User'
resolves correctly and django.contrib.auth and django.contrib.admin
migrations can attach their foreign-key dependencies to accounts.User.

The build command `migrate --fake-initial` will mark this migration as
applied without executing DDL, because the underlying tables already exist
and the models are unmanaged.
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('industry', models.CharField(max_length=100)),
                ('size_bracket', models.CharField(choices=[
                    ('1-25', '1-25 employees'),
                    ('26-100', '26-100 employees'),
                    ('101-500', '101-500 employees'),
                    ('501-2000', '501-2,000 employees'),
                    ('2001-5000', '2,001-5,000 employees'),
                    ('5000+', '5,000+ employees'),
                ], max_length=20)),
                ('employee_count_estimate', models.IntegerField(blank=True, null=True)),
                ('geographic_scope', models.CharField(blank=True, max_length=50)),
                ('revenue_bracket', models.CharField(blank=True, max_length=50)),
                ('primary_regulations', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'companies',
                'db_table': 'companies',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('name', models.CharField(blank=True, max_length=255)),
                ('role', models.CharField(blank=True, max_length=100)),
                ('title', models.CharField(blank=True, max_length=255)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('email_verified_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_login_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='accounts.company')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'db_table': 'users',
                'managed': False,
            },
        ),
    ]
