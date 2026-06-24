"""User and Company models for the SRJ AI Audit Platform.

These models map to the existing companies and users tables created via
the srj-mcp PostgreSQL bootstrap migration on 2026-06-23. The Meta
managed=False directive prevents Django from attempting to recreate
them during initial migration; ownership transfers to Django via
`python manage.py migrate --fake-initial` on first deployment.

The User model intentionally extends AbstractBaseUser rather than
AbstractUser because the underlying users table tracks email/password
authentication only — Django auth's username/first_name/last_name
fields are not present. AbstractBaseUser provides the cryptographic
password machinery (check_password, set_password, etc.) without
adding columns we don't have.
"""
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Company(models.Model):
    """A buyer's company. One company can have multiple users and multiple engagements."""

    SIZE_CHOICES = [
        ('1-25', '1-25 employees'),
        ('26-100', '26-100 employees'),
        ('101-500', '101-500 employees'),
        ('501-2000', '501-2,000 employees'),
        ('2001-5000', '2,001-5,000 employees'),
        ('5000+', '5,000+ employees'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100)
    size_bracket = models.CharField(max_length=20, choices=SIZE_CHOICES)
    employee_count_estimate = models.IntegerField(null=True, blank=True)
    geographic_scope = models.CharField(max_length=50, blank=True)
    revenue_bracket = models.CharField(max_length=50, blank=True)
    primary_regulations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'
        managed = False  # Created via srj-mcp bootstrap migration
        verbose_name_plural = 'companies'
        indexes = [
            models.Index(fields=['industry']),
            models.Index(fields=['size_bracket']),
        ]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Custom manager because USERNAME_FIELD is email, not username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """A buyer (Tier 1, 2, or 3). Distinct from Respondent records, which
    represent people answering questions and live in the respondents table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    role = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    last_login_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        managed = False  # Created via srj-mcp bootstrap migration

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.name or self.email

    def get_short_name(self):
        return self.name.split()[0] if self.name else self.email
