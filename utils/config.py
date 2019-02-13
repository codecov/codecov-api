import os

from yaml import load as yaml_load


class ConfigHelper(object):

    def __init__(self):
        self._params = None

    @property
    def params(self):
        if self._params is None:
            yaml_path = os.getenv('CODECOV_YML', '/config/codecov.yml')
            if os.path.exists(yaml_path):
                # load all configuration defaults
                with open(yaml_path, 'r') as c:
                    self._params = yaml_load(c.read())
            else:
                self._params = {}
        return self._params

    def get(self, *args, **kwargs):
        current_p = self.params
        for el in args:
            current_p = current_p[el]
        return current_p


config = ConfigHelper()


def get_config(*path, default=None):
    try:
        return config.get(*path)
    except Exception:
        return default


def get_verify_ssl(service):
    verify = get_config(service, 'verify_ssl')
    if verify is False:
        return False
    return get_config(service, 'ssl_pem') or os.getenv('REQUESTS_CA_BUNDLE')
