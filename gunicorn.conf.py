import logging
import os

from gunicorn.glogging import Logger
from prometheus_client import multiprocess


def child_exit(server, worker):
    if worker and worker.pid and "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        multiprocess.mark_process_dead(worker.pid)


class CustomGunicornLogger(Logger):
    """
    A custom class for logging gunicorn startup logs, these are for the logging that takes
    place before the Django app starts and takes over with its own defined logging formats.
    This class ensures the gunicorn minimum log level to be INFO instead of the default ERROR.
    """

    def setup(self, cfg):
        super().setup(cfg)
        custom_format = "[%(levelname)s] [%(process)d] [%(asctime)s] %(message)s "
        date_format = "%Y-%m-%d %H:%M:%S %z"
        formatter = logging.Formatter(fmt=custom_format, datefmt=date_format)

        # Update handlers with the custom formatter
        for handler in self.error_log.handlers:
            handler.setFormatter(formatter)
        for handler in self.access_log.handlers:
            handler.setFormatter(formatter)


logconfig_dict = {
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    }
}

logger_class = CustomGunicornLogger
