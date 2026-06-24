"""WSGI config for audit_platform project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'audit_platform.settings.production')

application = get_wsgi_application()
