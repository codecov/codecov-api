import os

from .settings_base import *

DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config(
    "setup", "api_allowed_hosts", default=["codecov.io-shadow", ".codecov.io"]
)
if THIS_POD_IP:
    ALLOWED_HOSTS.append(THIS_POD_IP)

WEBHOOK_URL = get_config("setup", "webhook_url", default="https://codecov.io")


STRIPE_API_KEY = os.environ.get("SERVICES__STRIPE__API_KEY", None)
STRIPE_ENDPOINT_SECRET = os.environ.get("SERVICES__STRIPE__ENDPOINT_SECRET", None)
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "price_1Gv2B8GlVGuVgOrkFnLunCgc",
    "users-pr-inappy": "price_1Gv2COGlVGuVgOrkuOYVLIj7",
    "users-sentrym": "price_1MlY9yGlVGuVgOrkHluurBtJ",
    "users-sentryy": "price_1MlYAYGlVGuVgOrke9SdbBUn",
    "users-enterprisey": "price_1LmjzwGlVGuVgOrkIwlM46EU",
    "users-enterprisem": "price_1LmjypGlVGuVgOrkzKtNqhwW",
    "users-teamm": "price_1NqPKdGlVGuVgOrkm9OFvtz8",
    "users-teamy": "price_1NrlXiGlVGuVgOrkgMTw5yno",
}

STRIPE_PLAN_VALS = {
    "price_1Gv2B8GlVGuVgOrkFnLunCgc": "users-pr-inappm",
    "price_1Gv2COGlVGuVgOrkuOYVLIj7": "users-pr-inappy",
    "price_1MlY9yGlVGuVgOrkHluurBtJ": "users-sentrym",
    "price_1MlYAYGlVGuVgOrke9SdbBUn": "users-sentryy",
    "price_1LmjzwGlVGuVgOrkIwlM46EU": "users-enterprisey",
    "price_1LmjypGlVGuVgOrkzKtNqhwW": "users-enterprisem",
    "price_1NqPKdGlVGuVgOrkm9OFvtz8": "users-teamm",
    "price_1NrlXiGlVGuVgOrkgMTw5yno": "users-teamy",
}

CORS_ALLOW_HEADERS += ["sentry-trace", "baggage"]
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url", default="https://codecov.io")
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)
CODECOV_DASHBOARD_URL = get_config(
    "setup", "codecov_dashboard_url", default="https://app.codecov.io"
)
CORS_ALLOWED_ORIGINS = [
    CODECOV_URL,
    CODECOV_DASHBOARD_URL,
    "https://gazebo.netlify.app",  # to access unreleased URL of gazebo
]
# We are also using the CORS settings to verify if the domain is safe to
# Redirect after authentication, update this setting with care
CORS_ALLOWED_ORIGIN_REGEXES = []

DATA_UPLOAD_MAX_MEMORY_SIZE = 15000000
SILENCED_SYSTEM_CHECKS = ["urls.W002"]

# Reinforcing the Cookie SameSite configuration to be sure it's Lax in prod
COOKIE_SAME_SITE = "Lax"

CSRF_TRUSTED_ORIGINS = [
    get_config("setup", "trusted_origin", default="https://*.codecov.io")
]
