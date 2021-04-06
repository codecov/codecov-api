from .settings_base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import os


DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["stage-api.codecov.dev"])
if THIS_POD_IP:
    ALLOWED_HOSTS.append(THIS_POD_IP)

WEBHOOK_URL = "https://stage-api.codecov.dev"


# TODO: there are secrets for these in the staging env -- why?
STRIPE_API_KEY = "sk_test_testsn3sc2tirvdea6mqp31t"
STRIPE_ENDPOINT_SECRET = "whsec_testzrff0orrbsv3bdekbbz8cz964dan"
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "plan_H6P3KZXwmAbqPS",
    "users-pr-inappy": "plan_H6P16wij3lUuxg",
}


sentry_sdk.init(
    dsn="https://570709366d674aeca773669feb989415@o26192.ingest.sentry.io/5215654",
    integrations=[DjangoIntegration()],
    environment="STAGING",
)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^(https:\/\/)?deploy-preview-\d+--codecov\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--stage-app\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--codecov-stage\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--gazebo\.netlify\.app$",
    r"^(https:\/\/)?\w+--gazebo\.netlify\.app$",
]
CORS_ALLOW_CREDENTIALS = True


CODECOV_URL = "https://stage-web.codecov.dev"
CODECOV_DASHBOARD_URL = "https://stage-app.codecov.dev"
CORS_ALLOWED_ORIGINS = [
    CODECOV_URL,
    CODECOV_DASHBOARD_URL,
    "https://gazebo.netlify.app",
]

DATA_UPLOAD_MAX_MEMORY_SIZE = 15000000
