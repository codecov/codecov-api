import os

from prometheus_client import multiprocess


def child_exit(server, worker):
    if worker and worker.pid and "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        multiprocess.mark_process_dead(worker.pid)
