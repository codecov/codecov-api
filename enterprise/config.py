from enum import Enum

from shared.config import get_config as shared_get_config

RUN_ENV = "ENTERPRISE"


class SettingsModule(Enum):
    ENTERPRISE = "codecov.settings_enterprise"
    DEV = None


def get_settings_module():
    return SettingsModule.ENTERPRISE.value


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
