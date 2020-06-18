from .settings_base import *
import logging


DEBUG = True
ALLOWED_HOSTS = ['localhost']


WEBHOOK_URL = '' # NGROK TUNNEL HERE


STRIPE_API_KEY = 'sk_test_testsn3sc2tirvdea6mqp31t'
STRIPE_PLAN_IDS = {
    "users-inappm": "plan_F50djuy2tOqnhp",
    "users-inappy": "plan_F50lRPhqk4zZFL"
}


# TODO: dev urls not defined yet -- but defining as such to make tests pass
CLIENT_PLAN_CHANGE_SUCCESS_URL = 'http://localhost:9000'
CLIENT_PLAN_CHANGE_CANCEL_URL = 'http://localhost:9000'


CORS_ORIGIN_WHITELIST = ['localhost:9000']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'localhost'
