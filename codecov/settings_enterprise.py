from .settings_base import *
import os
from utils.config import get_config, get_settings_module

DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["*"])
if THIS_POD_IP:
    ALLOWED_HOSTS.append(THIS_POD_IP)
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url")
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'codecov_auth.authentication.CodecovSessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'internal_api.pagination.StandardPageNumberPagination',
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'PAGE_SIZE': 20
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

CORS_ORIGIN_WHITELIST = get_config("setup", "api_cors_origin_whitelist", default=[DEFAULT_WHITELISTED_DOMAIN])
ALLOWED_HOSTS.append(DEFAULT_WHITELISTED_DOMAIN)
# only add api domain if it is different than codecov url
if API_DOMAIN != DEFAULT_WHITELISTED_DOMAIN:
    ALLOWED_HOSTS.append(API_DOMAIN)
# Referenced at module level of services/billing.py, so it needs to be defined
STRIPE_API_KEY = None
