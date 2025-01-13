import os

from utils.config import get_config

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

DEFAULT_TRUSTED_ORIGIN = None

# select out CODECOV_URL domain
if CODECOV_URL.startswith("https://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[8:]
elif CODECOV_URL.startswith("http://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[7:]
# select out CODECOV_API_URL domain
if CODECOV_API_URL.startswith("https://"):
    API_DOMAIN = CODECOV_API_URL[8:]
    DEFAULT_TRUSTED_ORIGIN = f"https://*.{API_DOMAIN}"
elif CODECOV_API_URL.startswith("http://"):
    API_DOMAIN = CODECOV_API_URL[7:]
    DEFAULT_TRUSTED_ORIGIN = f"http://*.{API_DOMAIN}"

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

BITBUCKET_REDIRECT_URI = get_config(
    "bitbucket", "redirect_uri", default=f"{CODECOV_URL}/login/bitbucket"
)
GITLAB_REDIRECT_URI = get_config(
    "gitlab", "redirect_uri", default=f"{CODECOV_URL}/login/gitlab"
)


GITLAB_ENTERPRISE_REDIRECT_URI = get_config(
    "gitlab_enterprise",
    "redirect_uri",
    default=f"{CODECOV_URL}/login/gle",
)

CODECOV_DASHBOARD_URL = get_config(
    "setup", "codecov_dashboard_url", default=CODECOV_URL
)

COOKIES_DOMAIN = get_config(
    "setup", "http", "cookies_domain", default=f".{DEFAULT_WHITELISTED_DOMAIN}"
)
SESSION_COOKIE_DOMAIN = COOKIES_DOMAIN

ADMINS_LIST = get_config("setup", "admins", default=[])

CSRF_TRUSTED_ORIGINS = [
    get_config("setup", "trusted_origin", default=DEFAULT_TRUSTED_ORIGIN)
]

GUEST_ACCESS = get_config("setup", "guest_access", default=True)

SHELTER_ENABLED = get_config("setup", "shelter_enabled", default=False)
