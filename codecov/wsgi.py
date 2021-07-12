"""
WSGI config for codecov project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

from open_telemetry import instrument

from utils.config import get_settings_module

os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module())

# install open telemetry tracing instrumentation in production environment
if os.environ.get('TRANSMIT_SPANS') is not None:
    instrument()

application = get_wsgi_application()
