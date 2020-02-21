import celery_config
from celery import Celery

from celery import signature, chain


celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


class TaskService(object):
    def __init__(self, queue='new_tasks'):
        self.queue = queue

    def _create_signature(self, name, args=None, kwargs=None):
        """
        Create Celery signature
        """
        return signature(name, args=args, kwargs=kwargs, queue=self.queue, app=celery_app)

    def status_set_pending(self, repoid, commitid, branch, on_a_pull_request):
        self._create_signature(
            'app.tasks.status.SetPending',
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                branch=branch,
                on_a_pull_request=on_a_pull_request
            )
        ).apply_async()

    def notify(self, repoid, commitid):
        self._create_signature(
            'app.tasks.notify.Notify',
            kwargs=dict(repoid=repoid, commitid=commitid)
        ).apply_async()
