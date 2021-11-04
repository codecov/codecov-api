"""
WSGI config for codecov project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

from utils.config import get_settings_module

os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module())
if (
    os.getenv("OPENTELEMETRY_ENDPOINT")
    and os.getenv("OPENTELEMETRY_TOKEN")
    and os.getenv("OPENTELEMETRY_CODECOV_RATE")
):
    from open_telemetry import instrument

    instrument()

application = get_wsgi_application()
