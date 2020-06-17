from .settings_base import *
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = ["api.codecov.io", THIS_POD_IP] if THIS_POD_IP else ["api.codecov.io"]
WEBHOOK_URL = 'https://codecov.io'
STRIPE_API_KEY = os.environ.get('SERVICES__STRIPE__API_KEY', None)
sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="PRODUCTION"
)
CORS_ORIGIN_WHITELIST = ['app.codecov.io']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'https://codecov.io'
