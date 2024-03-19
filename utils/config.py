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


def get_config(*path, default=None):
    return shared_get_config(*path, default=default)


def should_write_data_to_storage_config_check(
    master_switch_key: str, is_codecov_repo: bool, repoid: int
) -> bool:
    master_write_switch = get_config(
        "setup",
        "save_report_data_in_storage",
        master_switch_key,
        default=False,
    )
    if master_write_switch == "restricted_access":
        allowed_repo_ids = get_config(
            "setup", "save_report_data_in_storage", "repo_ids", default=[]
        )
        is_in_allowed_repoids = repoid in allowed_repo_ids
    elif master_write_switch == "general_access":
        is_in_allowed_repoids = True
    else:
        is_in_allowed_repoids = False
    return master_write_switch and (is_codecov_repo or is_in_allowed_repoids)
