from .settings_base import *
import logging


DEBUG = True
ALLOWED_HOSTS = ["localhost"]


WEBHOOK_URL = ""  # NGROK TUNNEL HERE


STRIPE_API_KEY = "sk_test_test5yu7aahw6kpo835ig37d8hh72m45cwAJDQLlXCGPMcdGM54WA7X3iDzwyOw2Vlnce3Q8cAQ3kyrHg25ubgJYW00B2fPnTea"
STRIPE_ENDPOINT_SECRET = "whsec_testzrff0orrbsv3bdekbbz8cz964dan"
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

GITLAB_CLIENT_ID = "testq117krewaffvh4y2ktl1cpof8ufldd397vygenzuy24wb220rqg83cdaps4w"
GITLAB_CLIENT_SECRET = (
    "testq19ki95gaa4faunz92a97otmekrwczg60s8wdy3vx1ddfch2rff2oagsozsr"
)


CODECOV_DASHBOARD_URL = "http://localhost:9000"

COOKIES_DOMAIN = "localhost"
