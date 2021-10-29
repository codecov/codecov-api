import logging
import os
from enum import Enum

from shared.config import get_config as shared_get_config


class SettingsModule(Enum):
    DEV = "codecov.settings_dev"
    STAGING = "codecov.settings_staging"
    TESTING = "codecov.settings_test"
    ENTERPRISE = "codecov.settings_enterprise"
    PRODUCTION = "codecov.settings_prod"


RUN_ENV = os.environ.get("RUN_ENV", "PRODUCTION")


if RUN_ENV == "DEV":
    settings_module = SettingsModule.DEV.value
elif RUN_ENV == "STAGING":
    settings_module = SettingsModule.STAGING.value
elif RUN_ENV == "TESTING":
    settings_module = SettingsModule.TESTING.value
elif RUN_ENV == "ENTERPRISE":
    settings_module = SettingsModule.ENTERPRISE.value
else:
    settings_module = SettingsModule.PRODUCTION.value


def get_settings_module():
    return settings_module


class MissingConfigException(Exception):
    pass


log = logging.getLogger(__name__)


def get_config(*path, default=None):
    return shared_get_config(*path, default=default)
