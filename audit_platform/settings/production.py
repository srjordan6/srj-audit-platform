"""Production settings — security hardened, Sentry enabled."""
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401,F403

DEBUG = False

# Redis-backed cache — required for the rate-limiter in bot_protection.py
# to share counter state across gunicorn workers. Falls back to LocMem
# (per-process) if REDIS_URL is missing; still functional in dev.
_redis_url = env('REDIS_URL', default='')  # noqa: F405
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'TIMEOUT': 3600,
        },
    }

# Security headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# Behind a Cloudflare Worker reverse proxy at aiauditforcompanies.com.
# The Worker sets Host = <render-internal> so ALLOWED_HOSTS matches, and
# forwards X-Forwarded-Host / X-Forwarded-Proto carrying the branded origin.
USE_X_FORWARDED_HOST = True

# CSRF checks the request Origin/Referer against this list on POST.
# Browsers send Origin = https://aiauditforcompanies.com from the branded
# domain; that must be trusted or Django 4+ returns 403.
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://aiauditforcompanies.com',
        'https://www.aiauditforcompanies.com',
        'https://srj-audit-web-gor5.onrender.com',
    ],
)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# Sentry
SENTRY_DSN = env('SENTRY_DSN', default='')  # noqa: F405
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=env('SENTRY_ENVIRONMENT', default='production'),  # noqa: F405
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
