from contextlib import suppress
from json import dumps, loads
import logging

from celery import Celery
from celery import signature, chain
from celery.result import result_from_tuple
from services.redis_configuration import get_redis_connection

import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


log = logging.getLogger(__name__)


class TaskService(object):
    def __init__(self, queue="new_tasks"):
        self.queue = queue

    def _create_signature(self, name, args=None, kwargs=None):
        """
        Create Celery signature
        """
        return signature(
            name, args=args, kwargs=kwargs, queue=self.queue, app=celery_app
        )

    def status_set_pending(self, repoid, commitid, branch, on_a_pull_request):
        self._create_signature(
            "app.tasks.status.SetPending",
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                branch=branch,
                on_a_pull_request=on_a_pull_request,
            ),
        ).apply_async()

    def upload(self, repoid, commitid, countdown=0, debug=False, rebuild=False):
        self._create_signature(
            "app.tasks.upload.Upload",
            kwargs=dict(repoid=repoid, commitid=commitid, debug=debug, rebuild=rebuild),
        ).apply_async(countdown=countdown)

    def notify(self, repoid, commitid, current_yaml=None):
        self._create_signature(
            "app.tasks.notify.Notify",
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                current_yaml=current_yaml,
            ),
        ).apply_async()

    def pulls_sync(self, repoid, pullid):
        self._create_signature(
            "app.tasks.pulls.Sync",
            kwargs=dict(
                repoid=repoid,
                pullid=pullid,
            ),
        ).apply_async()

    def is_refreshing(self, ownerid):
        redis = get_redis_connection()
        with suppress(ValueError):
            data_task = redis.hget("refresh", ownerid)
            result = result_from_tuple(loads(data_task))
            if not result.ready():
                return True
        redis.hdel("refresh", ownerid)
        return False

    def refresh(
        self,
        ownerid,
        username,
        sync_teams=True,
        sync_repos=True,
        using_integration=False,
    ):
        """
        Send sync_teams and/or sync_repos task message

        If running both tasks on new worker, we create a chain with sync_teams to run
        first so that when sync_repos starts it has the most up to date teams/groups
        data for the user. Otherwise, we may miss some repos.
        """

        if self.is_refreshing(ownerid):
            # If a refresh is already running for that user, we skip
            return

        chain_to_call = []
        kwargs = dict(
            ownerid=ownerid,
            username=username,
            using_integration=using_integration,
        )
        if sync_teams:
            task = self._create_signature(
                "app.tasks.sync_teams.SyncTeams",
                kwargs=kwargs,
            )
            chain_to_call.append(task)

        if sync_repos:
            task = self._create_signature(
                "sync_repos.SyncRepos",
                kwargs=kwargs,
            )
            chain_to_call.append(task)

        resp = chain(*chain_to_call).apply_async()
        # store in redis the task data to be used for `is_refreshing` logic
        redis = get_redis_connection()
        redis.hset("refresh", ownerid, dumps(resp.as_tuple()))

    def sync_plans(self, sender=None, account=None, action=None):
        self._create_signature(
            "app.tasks.ghm_sync_plans.SyncPlans",
            kwargs=dict(sender=sender, account=account, action=action),
        )

    def delete_owner(self, ownerid):
        log.info(f"Triggering delete_owner task for owner: {ownerid}")
        self._create_signature(
            "app.tasks.delete_owner.DeleteOwner", kwargs=dict(ownerid=ownerid)
        )
