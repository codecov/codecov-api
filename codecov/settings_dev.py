import logging

from .settings_base import *

DEBUG = True
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["localhost"])


WEBHOOK_URL = ""  # NGROK TUNNEL HERE


STRIPE_API_KEY = "sk_test_testurtke3v89d4udnesfxh413qnioseSuuwkdBMDvk4ZLesyoD4sSUoG4XDkPXsjN9MzRPaeylnqbgIOhnFI9Urg00BTUxkOh1"
STRIPE_ENDPOINT_SECRET = "whsec_testaln4a44tnbpj25h10d8fobw37m6f"
STRIPE_PLAN_IDS = {
    "users-pr-inappm": "plan_H6P3KZXwmAbqPS",
    "users-pr-inappy": "plan_H6P16wij3lUuxg",
}

CORS_ALLOWED_ORIGINS = ["http://localhost:9000", "http://localhost"]
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = "localhost"


GITHUB_CLIENT_ID = "3d44be0e772666136a13"
GITHUB_CLIENT_SECRET = "testrjumu7w1dfvxbr23q9sx3c7u3hgftcf1uho8"
GITHUB_BOT_KEY = "testjltl8ckrcduovemrhp7upoqzs2sovquv9fzk"

BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
BITBUCKET_REDIRECT_URI = "localhost:8000"

GITLAB_CLIENT_ID = "testq117krewaffvh4y2ktl1cpof8ufldd397vygenzuy24wb220rqg83cdaps4w"
GITLAB_CLIENT_SECRET = (
    "testq19ki95gaa4faunz92a97otmekrwczg60s8wdy3vx1ddfch2rff2oagsozsr"
)


CODECOV_DASHBOARD_URL = "http://localhost:3000"

CORS_ALLOWED_ORIGINS = [
    CODECOV_DASHBOARD_URL,
    "http://localhost",
    "http://localhost:9000",
]

COOKIES_DOMAIN = "localhost"
SESSION_COOKIE_DOMAIN = "localhost"

GRAPHQL_PLAYGROUND = True

LOGGING = {
    "version": 1,
    "filters": {"require_debug_true": {"()": "django.utils.log.RequireDebugTrue",}},
    "formatters": {"console": {"format": "%(name)-12s %(levelname)-8s %(message)s"},},
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "formatter": "console",
            "class": "logging.StreamHandler",
        }
    },
    "loggers": {
        # 'django.db.backends': {
        #     'level': 'DEBUG',
        #     'handlers': ['console'],
        # }
    },
}
