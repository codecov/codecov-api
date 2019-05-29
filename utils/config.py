import os
import logging

from yaml import load as yaml_load
import collections

log = logging.getLogger(__name__)

default_config = {
    'services': {
        'minio': {
            'access_key_id': 'codecov-default-key',
            'secret_access_key': 'codecov-default-secret',
            'verify_ssl': False,
            'hash_key': None,
            'bucket': 'archive',
            'region': 'us-east-1'
        },
        'database_url': 'postgres://postgres:@postgres:5432/postgres'
    },
    'setup': {
        'http': {
            'timeouts': {
                'connect': 15,
                'receive': 30
            },
            'cookie_secret': 'abc123'
        },
        'tasks': {
            'celery': {
                'prefetch': 4,
                'soft_timelimit': 400,
                'hard_timelimit': 480,
                'default_queue': 'celery'
            }
        },
        'encryption_secret': ''
    }
}

class NotSetConfig(Exception):
    pass


def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class ConfigHelper(object):

    def __init__(self):
        self._params = None

    @property
    def params(self):
        if self._params is None:
            content = self.yaml_content()
            content = self.update_from_env(content)
            final_result = update(default_config, content)
            self.set_params(final_result)
        return self._params

    def update_from_env(self, content):
        return content

    def set_params(self, val):
        self._params = val

    def get(self, *args, **kwargs):
        current_p = self.params
        try:
            for el in args:
                current_p = current_p[el]
            return current_p
        except KeyError:
            raise NotSetConfig()

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
    except NotSetConfig:
        return default
