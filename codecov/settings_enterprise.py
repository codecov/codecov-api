from .settings_base import *
import os
from utils.config import get_config, get_settings_module

DEBUG = False
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts", default=["*"])
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url")

# select out CODECOV_URL domain
DEFAULT_WHITELISTED_DOMAIN = CODECOV_URL

CORS_ALLOWED_ORIGINS = get_config("setup", "api_CORS_ALLOWED_ORIGINS", default=[DEFAULT_WHITELISTED_DOMAIN])

# Referenced at module level of services/billing.py, so it needs to be defined
STRIPE_API_KEY = None
