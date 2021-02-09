from .settings_base import *
import os
from utils.config import get_config, get_settings_module

DEBUG = False
THIS_POD_IP = os.environ.get("THIS_POD_IP")
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["*"])
if THIS_POD_IP
    ALLOWED_HOSTS.append(THIS_POD_IP)
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url")

# select out CODECOV_URL domain
if CODECOV_URL.startswith("https://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[8:]
elif CODECOV_URL.startswith("http://"):
    DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL[7:]

CORS_ORIGIN_WHITELIST = get_config("setup", "api_cors_origin_whitelist", default=[DEFAULT_WHITELISTED_DOMAIN])

# Referenced at module level of services/billing.py, so it needs to be defined
STRIPE_API_KEY = None
