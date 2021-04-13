import os
import logging
import collections
from enum import Enum
from yaml import load as yaml_load
from copy import deepcopy


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

default_config = {
    "services": {
        "minio": {
            "access_key_id": "codecov-default-key",
            "secret_access_key": "codecov-default-secret",
            "verify_ssl": False,
            "hash_key": None,
            "bucket": "archive",
            "region": "us-east-1",
            "host": "minio",
            "port": 9000,
        },
        "database_url": "postgres://postgres:@postgres:5432/postgres",
        "redis_url": "redis://redis:6379/0",
    },
    "setup": {
        "http": {"timeouts": {"connect": 15, "receive": 30}, "cookie_secret": "abc123"},
        "encryption_secret": ""
    },
}


def update(d, u):
    d = deepcopy(d)
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class ConfigHelper(object):
    def __init__(self):
        self._params = None

    # Load config values from environment variables that are passed (and set) in GCP
    def load_env_var(self):
        val = {}
        for env_var in os.environ:
            # Split env variables on "__" to get values for nested config fields
            # For example: ONE__TWO__THREE='value' --> { 'one': { 'two': { 'three': 'value' }}}
            multiple_level_vars = env_var.split("__")
            if len(multiple_level_vars) > 1:
                current = val
                for c in multiple_level_vars[:-1]:
                    current = current.setdefault(c.lower(), {})
                current[multiple_level_vars[-1].lower()] = os.getenv(env_var)
        return val

    @property
    def params(self):
        """
            Construct the config by combining default values (defined above in "default_config"), yaml config, and OS env vars.
            An env var overrides a yaml config value, which overrides the default values.
        """
        if self._params is None:
            content = self.yaml_content()
            env_vars = self.load_env_var()
            temp_result = update(default_config, content)
            final_result = update(temp_result, env_vars)
            self.set_params(final_result)
        return self._params

    def set_params(self, val):
        self._params = val

    def get(self, *args, **kwargs):
        current_p = self.params
        for el in args:
            try:
                current_p = current_p[el]
            except KeyError:
                raise MissingConfigException(args)
        return current_p

    def yaml_content(self):
        yaml_path = os.getenv("CODECOV_YML", "/config/codecov.yml")
        try:
            with open(yaml_path, "r") as c:
                return yaml_load(c.read())
        except FileNotFoundError:
            return {}


config = ConfigHelper()


def get_config(*path, default=None):
    try:
        return config.get(*path)
    except MissingConfigException:
        return default
