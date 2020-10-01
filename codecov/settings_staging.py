from .settings_base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import os


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = ['stage-api.codecov.dev', THIS_POD_IP] if THIS_POD_IP else ['stage-api.codecov.dev']
WEBHOOK_URL = 'https://stage-api.codecov.dev'


# TODO: there are secrets for these in the staging env -- why?
STRIPE_API_KEY = 'sk_test_testsn3sc2tirvdea6mqp31t'
STRIPE_ENDPOINT_SECRET = "whsec_testzrff0orrbsv3bdekbbz8cz964dan"
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "plan_H6P3KZXwmAbqPS",
    "users-pr-inappy": "plan_H6P16wij3lUuxg"
}


sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="STAGING"
)


# TODO: stage urls not defined yet
CLIENT_PLAN_CHANGE_SUCCESS_URL = ''
CLIENT_PLAN_CHANGE_CANCEL_URL = ''


CORS_ORIGIN_WHITELIST = ["stage-app.codecov.dev", "stage-web.codecov.dev"]
CORS_ORIGIN_REGEX_WHITELIST = [r"^(https:\/\/)?deploy-preview-\d+--codecov\.netlify\.app$"]
CORS_ALLOW_CREDENTIALS = True


CODECOV_URL = 'https://stage-web.codecov.dev'
CODECOV_DASHBOARD_URL = 'https://stage-app.codecov.dev'
