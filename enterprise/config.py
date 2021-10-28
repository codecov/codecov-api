from enum import Enum

from shared.config import get_config as shared_get_config


class SettingsModule(Enum):
    ENTERPRISE = "codecov.settings_enterprise"
    DEV = None


def get_settings_module():
    return SettingsModule.ENTERPRISE.value


def get_config(*path, default=None):
    return shared_get_config(*path, default=default)
