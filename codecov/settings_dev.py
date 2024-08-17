import logging

from .settings_base import *

# Remove CSP headers from local development build to allow GQL Playground
MIDDLEWARE.remove("csp.middleware.CSPMiddleware")

DEBUG = True
# for shelter add "host.docker.internal" and make sure to map it to localhost
# in your /etc/hosts
ALLOWED_HOSTS = get_config(
    "setup",
    "api_allowed_hosts",
    default=["localhost", "api.lt.codecov.dev", "host.docker.internal"],
)

WEBHOOK_URL = ""  # NGROK TUNNEL HERE

STRIPE_API_KEY = get_config("services", "stripe", "api_key", default="default")
STRIPE_ENDPOINT_SECRET = get_config(
    "services", "stripe", "endpoint_secret", default="default"
)
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "plan_H6P3KZXwmAbqPS",
    "users-pr-inappy": "plan_H6P16wij3lUuxg",
    "users-sentrym": "price_1Mj1kYGlVGuVgOrk7jucaZAa",
    "users-sentryy": "price_1Mj1mMGlVGuVgOrkC0ORc6iW",
    "users-teamm": "price_1OCM0gGlVGuVgOrkWDYEBtSL",
    "users-teamy": "price_1OCM2cGlVGuVgOrkMWUFjPFz",
}

STRIPE_PLAN_VALS = {
    "plan_H6P3KZXwmAbqPS": "users-pr-inappm",
    "plan_H6P16wij3lUuxg": "users-pr-inappy",
    "price_1Mj1kYGlVGuVgOrk7jucaZAa": "users-sentrym",
    "price_1Mj1mMGlVGuVgOrkC0ORc6iW": "users-sentryy",
    "price_1OCM0gGlVGuVgOrkWDYEBtSL": "users-teamm",
    "price_1OCM2cGlVGuVgOrkMWUFjPFz": "users-teamy",
}

CORS_ALLOW_CREDENTIALS = True

CODECOV_URL = "localhost"
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)
CODECOV_DASHBOARD_URL = "http://localhost:3000"

CORS_ALLOWED_ORIGINS = [
    CODECOV_DASHBOARD_URL,
    "http://localhost",
    "http://localhost:9000",
]

COOKIES_DOMAIN = "localhost"
SESSION_COOKIE_DOMAIN = "localhost"

# add for shelter
# SHELTER_SHARED_SECRET = "test-supertoken"

GUEST_ACCESS = True
