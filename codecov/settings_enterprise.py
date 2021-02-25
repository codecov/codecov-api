from .settings_base import *
import os
from utils.config import get_config, get_settings_module

DEBUG = False
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["*"])
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url")


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

CORS_ORIGIN_WHITELIST = get_config("setup", "api_cors_origin_whitelist", default=[DEFAULT_WHITELISTED_DOMAIN])

# Referenced at module level of services/billing.py, so it needs to be defined
STRIPE_API_KEY = None
