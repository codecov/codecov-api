from celery.result import result_from_tuple
from contextlib import suppress
from json import dumps, loads

from services.redis_configuration import get_redis_connection
from services.task import TaskService, celery_app


class RefreshService(object):
    def __init__(self):
        self.task_service = TaskService()
        self.redis = get_redis_connection()

    def is_refreshing(self, ownerid):
        data_task = self.redis.hget("refresh", ownerid)
        if not data_task:
            return False
        try:
            res = result_from_tuple(loads(data_task), app=celery_app)
        except ValueError:
            self.redis.hdel("refresh", ownerid)
            return False
        has_failed = res.failed() or (res.parent and res.parent.failed())
        if res.successful() or has_failed:
            self.redis.hdel("refresh", ownerid)
            return False
        # task is not success, nor failed, so probably pending or in progress
        return True

    def trigger_refresh(
        self,
        ownerid,
        username,
        sync_teams=True,
        sync_repos=True,
        using_integration=False,
    ):
        if self.is_refreshing(ownerid):
            return
        resp = self.task_service.refresh(
            ownerid, username, sync_repos, sync_teams, using_integration
        )
        # store in redis the task data to be used for `is_refreshing` logic
        self.redis.hset("refresh", ownerid, dumps(resp.as_tuple()))
