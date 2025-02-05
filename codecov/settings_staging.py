import os

from .settings_base import *

DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config(
    "setup", "api_allowed_hosts", default=["stage-api.codecov.dev"]
)
if THIS_POD_IP:
    ALLOWED_HOSTS.append(THIS_POD_IP)

WEBHOOK_URL = get_config(
    "setup", "webhook_url", default="https://stage-api.codecov.dev"
)

STRIPE_API_KEY = os.environ.get("SERVICES__STRIPE__API_KEY", None)
STRIPE_ENDPOINT_SECRET = os.environ.get("SERVICES__STRIPE__ENDPOINT_SECRET", None)
COOKIES_DOMAIN = ".codecov.dev"
SESSION_COOKIE_DOMAIN = ".codecov.dev"

CORS_ALLOW_HEADERS += ["sentry-trace", "baggage"]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^(https:\/\/)?deploy-preview-\d+--codecov\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--stage-app\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--codecov-stage\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--gazebo\.netlify\.app$",
    r"^(https:\/\/)?deploy-preview-\d+--gazebo-staging\.netlify\.app$",
    r"^(https:\/\/)?\w+--gazebo\.netlify\.app$",
    r"^(https:\/\/)?preview-[\w\d\-]+\.codecov\.dev$",
]
CORS_ALLOW_CREDENTIALS = True

CODECOV_URL = get_config(
    "setup", "codecov_url", default="https://stage-web.codecov.dev"
)
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)
CODECOV_DASHBOARD_URL = get_config(
    "setup", "codecov_dashboard_url", default="https://stage-app.codecov.dev"
)
CORS_ALLOWED_ORIGINS = [
    CODECOV_URL,
    CODECOV_DASHBOARD_URL,
    "https://gazebo.netlify.app",
    "https://gazebo-staging.netlify.app",
    "http://localhost:3000",
]

# 25MB in bytes
DATA_UPLOAD_MAX_MEMORY_SIZE = 26214400

GRAPHQL_RATE_LIMIT_RPM = get_config("setup", "graphql", "rate_limit_rpm", default=1000)

# Same site is set to none on Staging as we want to be able to call the API
# From Netlify preview deploy
COOKIE_SAME_SITE = "None"
SESSION_COOKIE_SAMESITE = "None"

GCS_BUCKET_NAME = get_config("services", "minio", "bucket", default="codecov-staging")

CSRF_TRUSTED_ORIGINS = [
    get_config("setup", "trusted_origin", default="https://*.codecov.dev")
]

GRAPHQL_INTROSPECTION_ENABLED = True
