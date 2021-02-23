from .settings_base import *
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = ["codecov.io-shadow", ".codecov.io", THIS_POD_IP] if THIS_POD_IP else [".codecov.io"]


INSTALLED_APPS += [
    'ddtrace.contrib.django'
]


WEBHOOK_URL = 'https://codecov.io'


STRIPE_API_KEY = os.environ.get('SERVICES__STRIPE__API_KEY', None)
STRIPE_ENDPOINT_SECRET = os.environ.get("SERVICES__STRIPE__ENDPOINT_SECRET", None)
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "price_1Gv2B8GlVGuVgOrkFnLunCgc",
    "users-pr-inappy": "price_1Gv2COGlVGuVgOrkuOYVLIj7"
}


sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="PRODUCTION"
)

CORS_ORIGIN_WHITELIST = ['app.codecov.io', 'codecov.io']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'https://codecov.io'
CODECOV_DASHBOARD_URL = 'https://app.codecov.io'

DATA_UPLOAD_MAX_MEMORY_SIZE = 15000000
