import logging

from .settings_base import *

DEBUG = True
ALLOWED_HOSTS = get_config(
    "setup", "api_allowed_hosts", default=["localhost", "local-api-stripe.ngrok.io"]
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
}

CORS_ALLOW_CREDENTIALS = True

CODECOV_URL = "localhost"
CODECOV_DASHBOARD_URL = "http://localhost:3000"

CORS_ALLOWED_ORIGINS = [
    CODECOV_DASHBOARD_URL,
    "http://localhost",
    "http://localhost:9000",
]

COOKIES_DOMAIN = "localhost"
SESSION_COOKIE_DOMAIN = "localhost"

GRAPHQL_PLAYGROUND = True
