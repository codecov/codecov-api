import os
from urllib.parse import urlparse

from utils.config import get_config, get_settings_module

from .settings_base import *

DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["*"])
if THIS_POD_IP:
    ALLOWED_HOSTS.append(THIS_POD_IP)
CORS_ALLOW_CREDENTIALS = True
# Setting default to localhost to avoid errors when running compilation steps.
# This is "fine" because the app surely won't be in a working state without a valid url.
CODECOV_URL = get_config("setup", "codecov_url", default="http://localhost")
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)

db_url = get_config("services", "database_url")
db_conf = urlparse(db_url)
DATABASE_USER = db_conf.username
DATABASE_NAME = db_conf.path.replace("/", "")
DATABASE_PASSWORD = db_conf.password
DATABASE_HOST = db_conf.hostname
DATABASE_PORT = db_conf.port


# this is the time in seconds django decides to keep the connection open after the request
# the default is 0 seconds, meaning django closes the connection after every request
# https://docs.djangoproject.com/en/3.1/ref/settings/#conn-max-age
CONN_MAX_AGE = int(get_config("services", "database", "conn_max_age", default=0))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DATABASE_NAME,
        "USER": DATABASE_USER,
        "PASSWORD": DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "PORT": DATABASE_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "codecov_auth.authentication.CodecovSessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "internal_api.pagination.StandardPageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "PAGE_SIZE": 20,
}


# select out CODECOV_URL domain
if CODECOV_URL.startswith("https://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[8:]
elif CODECOV_URL.startswith("http://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[7:]
# select out CODECOV_API_URL domain
if CODECOV_API_URL.startswith("https://"):
    API_DOMAIN = CODECOV_API_URL[8:]
elif CODECOV_API_URL.startswith("http://"):
    API_DOMAIN = CODECOV_API_URL[7:]

CORS_ALLOWED_ORIGINS = get_config(
    "setup", "api_cors_allowed_origins", default=[CODECOV_URL]
)
ALLOWED_HOSTS.append(DEFAULT_WHITELISTED_DOMAIN)
# only add api domain if it is different than codecov url
if API_DOMAIN != DEFAULT_WHITELISTED_DOMAIN:
    ALLOWED_HOSTS.append(API_DOMAIN)
# Referenced at module level of services/billing.py, so it needs to be defined
STRIPE_API_KEY = None
SILENCED_SYSTEM_CHECKS = ["urls.W002"]
UPLOAD_THROTTLING_ENABLED = False
