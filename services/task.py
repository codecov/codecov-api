import logging

from celery import Celery, chain, signature
from shared import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object("shared.celery_config:BaseCeleryConfig")

log = logging.getLogger(__name__)


class TaskService(object):
    def _create_signature(self, name, args=None, kwargs=None):
        """
        Create Celery signature
        """
        return signature(name, args=args, kwargs=kwargs, app=celery_app)

    def compute_comparison(self, comparison_id):
        self._create_signature(
            celery_config.compute_comparison_task_name,
            kwargs=dict(comparison_id=comparison_id),
        ).apply_async()

    def normalize_profiling_upload(self, profiling_upload_id):
        return self._create_signature(
            celery_config.profiling_normalization_task_name,
            kwargs=dict(profiling_upload_id=profiling_upload_id),
        ).apply_async(countdown=10)

    def collect_profiling_commit(self, profiling_commit_id):
        return self._create_signature(
            celery_config.profiling_collection_task_name,
            kwargs=dict(profiling_id=profiling_commit_id),
        ).apply_async()

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
            kwargs=dict(repoid=repoid, commitid=commitid, current_yaml=current_yaml,),
        ).apply_async()

    def pulls_sync(self, repoid, pullid):
        self._create_signature(
            "app.tasks.pulls.Sync", kwargs=dict(repoid=repoid, pullid=pullid,),
        ).apply_async()

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
        chain_to_call = []
        if sync_teams:
            chain_to_call.append(
                self._create_signature(
                    "app.tasks.sync_teams.SyncTeams",
                    kwargs=dict(
                        ownerid=ownerid,
                        username=username,
                        using_integration=using_integration,
                    ),
                )
            )

        if sync_repos:
            chain_to_call.append(
                self._create_signature(
                    "app.tasks.sync_repos.SyncRepos",
                    kwargs=dict(
                        ownerid=ownerid,
                        username=username,
                        using_integration=using_integration,
                    ),
                )
            )

        return chain(*chain_to_call).apply_async()

    def sync_plans(self, sender=None, account=None, action=None):
        self._create_signature(
            "app.tasks.ghm_sync_plans.SyncPlans",
            kwargs=dict(sender=sender, account=account, action=action),
        ).apply_async()

    def delete_owner(self, ownerid):
        log.info(f"Triggering delete_owner task for owner: {ownerid}")
        self._create_signature(
            "app.tasks.delete_owner.DeleteOwner", kwargs=dict(ownerid=ownerid)
        )
