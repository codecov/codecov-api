from .settings_base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DEBUG = False
ALLOWED_HOSTS = ['stage-api.codecov.dev']
WEBHOOK_URL = 'https://stage-api.codecov.dev'
STRIPE_API_KEY = 'sk_test_testsn3sc2tirvdea6mqp31t'
sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="STAGING"
)

CORS_ORIGIN_WHITELIST = ['deploy-preview-*--zen-dubinsky-9aced3.netlify.app']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'https://stage-web.codecov.dev'
