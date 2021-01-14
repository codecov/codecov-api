from .settings_base import *
import os
from utils.config import get_config, get_settings_module

DEBUG = False
ALLOWED_HOSTS = get_config("setup", "api_allowed_hosts")
CORS_ORIGIN_WHITELIST = get_config("setup", "api_cors_origin_whitelist")
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = get_config("setup", "codecov_url")
