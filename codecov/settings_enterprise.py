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
CODECOV_DASHBOARD_URL = get_config(
    "setup", "codecov_dashboard_url", default=CODECOV_URL
)

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
BITBUCKET_REDIRECT_URI = get_config(
    "bitbucket", "redirect_uri", default=f"{CODECOV_URL}/login/bitbucket"
)
GITLAB_REDIRECT_URI = get_config(
    "gitlab", "redirect_uri", default=f"{CODECOV_URL}/login/gitlab"
)

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

COOKIES_DOMAIN = get_config(
    "setup", "http", "cookies_domain", default=f".{DEFAULT_WHITELISTED_DOMAIN}"
)
SESSION_COOKIE_DOMAIN = get_config(
    "setup", "http", "cookies_domain", default=f".{DEFAULT_WHITELISTED_DOMAIN}"
)
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
