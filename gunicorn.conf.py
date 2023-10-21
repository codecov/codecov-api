from prometheus_client import multiprocess


def child_exit(server, worker):
    if worker and worker.pid:
        multiprocess.mark_process_dead(worker.pid)
