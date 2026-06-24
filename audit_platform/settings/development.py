"""Development settings — local Postgres/Redis via Docker, DEBUG enabled."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ['*']

# Django Debug Toolbar (development only)
INSTALLED_APPS += ['debug_toolbar']  # noqa: F405
MIDDLEWARE.insert(  # noqa: F405
    1,  # after SecurityMiddleware
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)
INTERNAL_IPS = ['127.0.0.1']

# Use console email backend in development unless Postmark is explicitly configured
if not POSTMARK_API_TOKEN:  # noqa: F405
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
