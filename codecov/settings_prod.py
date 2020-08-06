from .settings_base import *
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = [".codecov.io", THIS_POD_IP] if THIS_POD_IP else [".codecov.io"]


WEBHOOK_URL = 'https://codecov.io'


STRIPE_API_KEY = os.environ.get('SERVICES__STRIPE__API_KEY', None)
STRIPE_ENDPOINT_SECRET = os.environ.get("SERVICES__STRIPE__ENDPOINT_SECRET", None)
STRIPE_PLAN_IDS = {
    "users-inappm": "plan_FZfyGRXwm8is1L",
    "users-inappy": "plan_FZfwfpAYWDks0V"
}


sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="PRODUCTION"
)


# TODO: prod URLs not defined yet
CLIENT_PLAN_CHANGE_SUCCESS_URL = ''
CLIENT_PLAN_CHANGE_CANCEL_URL = ''


CORS_ORIGIN_WHITELIST = ['app.codecov.io', 'codecov.io']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'https://codecov.io'
CODECOV_DASHBOARD_URL = 'https://app.codecov.io'
