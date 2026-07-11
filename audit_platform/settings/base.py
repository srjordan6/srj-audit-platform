"""Base settings for SRJ AI Audit Platform.

Imported by development.py and production.py. Defaults to development-friendly
values; production.py hardens the security-sensitive ones.

Schema note: tables companies, users, engagements, respondents, questions,
responses, scores, reports, documents, events, discount_credits, and
refund_requests were created via the srj-mcp PostgreSQL bootstrap migration
on 2026-06-23 (115 Tier 1 questions loaded). Django apps below use
managed=False where they map to those existing tables until the first
Django migration aligns ownership. Initial deployment uses
`python manage.py migrate --fake-initial` to register existing tables as
Django-tracked without recreating them.
"""
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Read .env if present (development convenience; ignored in production)
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env('SECRET_KEY', default='dev-only-insecure-key-replace-in-production')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'django_htmx',
    'django_rq',
    'crispy_forms',
    'crispy_bootstrap5',
    'storages',

    # Local apps
    'accounts',
    'engagements',
    'questionnaire',
    'scoring',
    'reports',
    'billing',
    'notifications',
    'analytics',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'audit_platform.urls'
WSGI_APPLICATION = 'audit_platform.wsgi.application'

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://postgres:devpass@localhost:5432/srj_audit',
    ),
}

RQ_QUEUES = {
    'default': {'URL': env('REDIS_URL', default='redis://localhost:6379/0')},
    'reports': {'URL': env('REDIS_URL', default='redis://localhost:6379/0')},
    'email':   {'URL': env('REDIS_URL', default='redis://localhost:6379/0')},
}

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Static files
# STATICFILES_DIRS tells collectstatic WHERE to look for source assets.
# Without this, `python manage.py collectstatic` won't pick up files under
# ./static/ (e.g. static/img/srj-logo.jpg) and {% static %} references will
# 404 in production. Only include the folder if it exists so dev environments
# without the folder don't crash Django startup with an ImproperlyConfigured.
_static_src = BASE_DIR / 'static'
STATICFILES_DIRS = [_static_src] if _static_src.exists() else []
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# CompressedManifestStaticFilesStorage would 500 on any {% static %} tag whose
# file wasn't collected (strict hash lookup). Use the non-manifest compressed
# storage while we're stabilizing the asset pipeline; switch back to Manifest
# once collectstatic is reliably green in CI.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# File storage (Backblaze B2 via S3 API). In dev, falls back to local FS
# if B2 credentials are not configured.
if env('B2_ACCESS_KEY_ID', default=''):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = env('B2_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = env('B2_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = env('B2_BUCKET_NAME', default='')
    AWS_S3_ENDPOINT_URL = env('B2_ENDPOINT_URL', default='')
    AWS_S3_REGION_NAME = env('B2_REGION', default='us-west-002')
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_FILE_OVERWRITE = False
else:
    MEDIA_ROOT = BASE_DIR / 'media'
    MEDIA_URL = '/media/'

# Email (Postmark in production; console backend in development)
POSTMARK_API_TOKEN = env('POSTMARK_API_TOKEN', default='')
DEFAULT_FROM_EMAIL = env('POSTMARK_FROM_EMAIL', default='audit@example.com')
if POSTMARK_API_TOKEN:
    EMAIL_BACKEND = 'postmarker.django.EmailBackend'
    POSTMARK = {'TOKEN': POSTMARK_API_TOKEN}
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Stripe
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')
STRIPE_IDENTITY_WEBHOOK_SECRET = env('STRIPE_IDENTITY_WEBHOOK_SECRET', default='')
TIER_1_REPORT_PRICE_CENTS = env.int('TIER_1_REPORT_PRICE_CENTS', default=39900)
STRIPE_IDENTITY_REQUIRED_THRESHOLD_EMPLOYEES = env.int(
    'STRIPE_IDENTITY_REQUIRED_THRESHOLD_EMPLOYEES', default=501
)

# AI narrative analysis (Claude API) - Phase 2a
# Empty ANTHROPIC_API_KEY silently disables the layer; reports still
# generate with template-only content.
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')
AI_ANALYSIS_MODEL = env('AI_ANALYSIS_MODEL', default='claude-sonnet-4-5')
AI_ANALYSIS_ENABLED = env.bool('AI_ANALYSIS_ENABLED', default=True)

# Platform configuration
PLATFORM_BASE_URL = env('PLATFORM_BASE_URL', default='http://localhost:8000')

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('DEFAULT_TIMEZONE', default='America/Chicago')
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms (Bootstrap 5)
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},  # Per Part A §2.8 security baseline
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
