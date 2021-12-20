import os
import sys

from django.core.wsgi import get_wsgi_application
from gunicorn.app.base import Application

from utils.config import get_settings_module


class StandaloneApplication(Application):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module())
    if len(sys.argv) > 1 and sys.argv[1] != "run":
        try:
            from django.core.management import execute_from_command_line
        except ImportError as exc:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            ) from exc
        execute_from_command_line(sys.argv)
    else:
        if len(sys.argv) > 2 and sys.argv[1] == "run":
            del sys.argv[1]
        application = get_wsgi_application()
        options = {
            "bind": "{0}:{1}".format(
                os.environ.get("CODECOV_API_BIND", "0.0.0.0"),
                os.environ.get("CODECOV_API_PORT", 8000),
            ),
            "accesslog": "-",
        }
        statsd_host = os.environ.get("STATSD_HOST", None)
        if statsd_host is not None:
            statsd_port = os.environ.get("STATSD_PORT", 8125)
            options["statsd_host"] = "{0}:{1}".format(statsd_host, statsd_port)
        StandaloneApplication(application, options).run()
