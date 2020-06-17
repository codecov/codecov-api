from .settings_base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import os


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = ['stage-api.codecov.dev', THIS_POD_IP] if THIS_POD_IP else ['stage-api.codecov.dev']
WEBHOOK_URL = 'https://stage-api.codecov.dev'
STRIPE_API_KEY = 'sk_test_testsn3sc2tirvdea6mqp31t'
sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="STAGING"
)

CORS_ORIGIN_REGEX_WHITELIST = [r"^https:\/\/deploy-preview-[0-9]+--zen-dubinsky-9aced3\.netlify\.app$"]
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'https://stage-web.codecov.dev'
