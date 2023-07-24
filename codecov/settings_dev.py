import logging

from .settings_base import *

DEBUG = True
ALLOWED_HOSTS = get_config(
    "setup", "api_allowed_hosts", default=["localhost", "local-api-stripe.ngrok.io"]
)

WEBHOOK_URL = ""  # NGROK TUNNEL HERE

STRIPE_API_KEY = "sk_test_testurtke3v89d4udnesfxh413qnioseSuuwkdBMDvk4ZLesyoD4sSUoG4XDkPXsjN9MzRPaeylnqbgIOhnFI9Urg00BTUxkOh1"
STRIPE_ENDPOINT_SECRET = "whsec_testv00ijzofmsvxcktfmna1duw9pn8b"
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "plan_H6P3KZXwmAbqPS",
    "users-pr-inappy": "plan_H6P16wij3lUuxg",
    "users-sentrym": "price_1Mj1kYGlVGuVgOrk7jucaZAa",
    "users-sentryy": "price_1Mj1mMGlVGuVgOrkC0ORc6iW",
}

CORS_ALLOW_CREDENTIALS = True

GITHUB_CLIENT_ID = "3d44be0e772666136a13"

CODECOV_URL = "localhost"
BITBUCKET_REDIRECT_URI = "localhost:8000"
CODECOV_DASHBOARD_URL = "http://localhost:3000"

CORS_ALLOWED_ORIGINS = [
    CODECOV_DASHBOARD_URL,
    "http://localhost",
    "http://localhost:9000",
]

COOKIES_DOMAIN = "localhost"
SESSION_COOKIE_DOMAIN = "localhost"

GRAPHQL_PLAYGROUND = True
