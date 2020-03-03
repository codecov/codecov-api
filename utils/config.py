import os
import logging
from copy import deepcopy

from yaml import load as yaml_load
import collections


class MissingConfigException(Exception):
    pass


log = logging.getLogger(__name__)

default_config = {
    'services': {
        'minio': {
            'access_key_id': 'codecov-default-key',
            'secret_access_key': 'codecov-default-secret',
            'verify_ssl': False,
            'hash_key': None,
            'bucket': 'archive',
            'region': 'us-east-1',
            'host': 'minio',
            'port': 9000
        },
        'database_url': 'postgres://postgres:@postgres:5432/postgres',
        "github": {
            "client_id": "3d44be0e772666136a13",
            "client_secret": "testrjumu7w1dfvxbr23q9sx3c7u3hgftcf1uho8"
        },
        "bitbucket": {
            "client_id": "testqmo19ebdkseoby",
            "client_secret": "testfi8hzehvz453qj8mhv21ca4rf83f"
        },
        "gitlab": {
            "client_id": "testq117krewaffvh4y2ktl1cpof8ufldd397vygenzuy24wb220rqg83cdaps4w",
            "client_secret": "testq19ki95gaa4faunz92a97otmekrwczg60s8wdy3vx1ddfch2rff2oagsozsr"
        },
        "redis_url": 'redis://redis:6379/0',
    },
    'setup': {
        'http': {
            'timeouts': {
                'connect': 15,
                'receive': 30
            },
            'cookie_secret': 'abc123'
        },
        'encryption_secret': '',
        'codecov_url': 'http://localhost:5100'
    }
}


def update(d, u):
    d = deepcopy(d)
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class ConfigHelper(object):

    def __init__(self):
        self._params = None

    def load_env_var(self):
        val = {}
        for env_var in os.environ:
            multiple_level_vars = env_var.split('__')
            if len(multiple_level_vars) > 1:
                current = val
                for c in multiple_level_vars[:-1]:
                    current = current.setdefault(c.lower(), {})
                current[multiple_level_vars[-1].lower()] = os.getenv(env_var)
        return val

    @property
    def params(self):
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
        yaml_path = os.getenv('CODECOV_YML', '/config/codecov.yml')
        try:
            with open(yaml_path, 'r') as c:
                return yaml_load(c.read())
        except FileNotFoundError:
            return {}


config = ConfigHelper()


def get_config(*path, default=None):
    try:
        return config.get(*path)
    except MissingConfigException:
        return default

