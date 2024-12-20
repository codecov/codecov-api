import logging
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple

import celery
from celery import Celery, chain, group, signature
from celery.canvas import Signature
from django.conf import settings
from sentry_sdk import set_tag
from sentry_sdk.integrations.celery import _wrap_apply_async
from shared import celery_config

from core.models import Repository
from services.task.task_router import route_task
from timeseries.models import Dataset, MeasurementName

celery_app = Celery("tasks")
celery_app.config_from_object("shared.celery_config:BaseCeleryConfig")

log = logging.getLogger(__name__)

if settings.SENTRY_ENV:
    celery.group.apply_async = _wrap_apply_async(celery.group.apply_async)
    celery.chunks.apply_async = _wrap_apply_async(celery.chunks.apply_async)
    celery.canvas._chain.apply_async = _wrap_apply_async(
        celery.canvas._chain.apply_async
    )
    celery.canvas._chord.apply_async = _wrap_apply_async(
        celery.canvas._chord.apply_async
    )
    Signature.apply_async = _wrap_apply_async(Signature.apply_async)


class TaskService(object):
    def _create_signature(self, name, args=None, kwargs=None, immutable=False):
        """
        Create Celery signature
        """
        queue_and_config = route_task(name, args=args, kwargs=kwargs)
        queue_name = queue_and_config["queue"]
        extra_config = queue_and_config.get("extra_config", {})
        celery_compatible_config = {
            "time_limit": extra_config.get("hard_timelimit", None),
            "soft_time_limit": extra_config.get("soft_timelimit", None),
        }
        headers = dict(created_timestamp=datetime.now().isoformat())
        set_tag("celery.queue", queue_name)
        return signature(
            name,
            args=args,
            kwargs=kwargs,
            app=celery_app,
            queue=queue_name,
            headers=headers,
            immutable=immutable,
            **celery_compatible_config,
        )

    def schedule_task(self, task_name, *, kwargs, apply_async_kwargs):
        return self._create_signature(
            task_name,
            kwargs=kwargs,
        ).apply_async(**apply_async_kwargs)

    def compute_comparison(self, comparison_id):
        self._create_signature(
            celery_config.compute_comparison_task_name,
            kwargs=dict(comparison_id=comparison_id),
        ).apply_async()

    def compute_comparisons(self, comparison_ids: List[int]):
        """
        Enqueue a batch of comparison tasks using a Celery group
        """
        if len(comparison_ids) > 0:
            queue_and_config = route_task(
                celery_config.compute_comparison_task_name,
                args=None,
                kwargs=dict(comparison_id=comparison_ids[0]),
            )
            celery_compatible_config = {
                "queue": queue_and_config["queue"],
                "time_limit": queue_and_config.get("extra_config", {}).get(
                    "hard_timelimit", None
                ),
                "soft_time_limit": queue_and_config.get("extra_config", {}).get(
                    "soft_timelimit", None
                ),
            }
            signatures = [
                signature(
                    celery_config.compute_comparison_task_name,
                    args=None,
                    kwargs=dict(comparison_id=comparison_id),
                    app=celery_app,
                    **celery_compatible_config,
                )
                for comparison_id in comparison_ids
            ]
            for comparison_id in comparison_ids:
                # log each separately so it can be filtered easily in the logs
                log.info(
                    "Triggering compute comparison task",
                    extra=dict(comparison_id=comparison_id),
                )
            group(signatures).apply_async()

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

    def upload_signature(
        self,
        repoid,
        commitid,
        report_type=None,
        report_code=None,
        arguments=None,
        debug=False,
        rebuild=False,
        immutable=False,
    ):
        return self._create_signature(
            "app.tasks.upload.Upload",
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                report_type=report_type,
                report_code=report_code,
                arguments=arguments,
                debug=debug,
                rebuild=rebuild,
            ),
            immutable=immutable,
        )

    def upload(
        self,
        repoid,
        commitid,
        report_type=None,
        report_code=None,
        arguments=None,
        countdown=0,
        debug=False,
        rebuild=False,
    ):
        return self.upload_signature(
            repoid,
            commitid,
            report_type=report_type,
            report_code=report_code,
            arguments=arguments,
            debug=debug,
            rebuild=rebuild,
        ).apply_async(countdown=countdown)

    def notify_signature(self, repoid, commitid, current_yaml=None, empty_upload=None):
        return self._create_signature(
            "app.tasks.notify.Notify",
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                current_yaml=current_yaml,
                empty_upload=empty_upload,
            ),
        )

    def notify(self, repoid, commitid, current_yaml=None, empty_upload=None):
        self.notify_signature(
            repoid, commitid, current_yaml=current_yaml, empty_upload=empty_upload
        ).apply_async()

    def pulls_sync(self, repoid, pullid):
        self._create_signature(
            "app.tasks.pulls.Sync", kwargs=dict(repoid=repoid, pullid=pullid)
        ).apply_async()

    def refresh(
        self,
        ownerid,
        username,
        sync_teams=True,
        sync_repos=True,
        using_integration=False,
        manual_trigger=False,
        repos_affected: Optional[List[Tuple[str, str]]] = None,
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
                        manual_trigger=manual_trigger,
                        repository_service_ids=repos_affected,
                    ),
                )
            )

        return chain(*chain_to_call).apply_async()

    def sync_plans(self, sender=None, account=None, action=None):
        self._create_signature(
            celery_config.ghm_sync_plans_task_name,
            kwargs=dict(sender=sender, account=account, action=action),
        ).apply_async()

    def delete_owner(self, ownerid):
        log.info(f"Triggering delete_owner task for owner: {ownerid}")
        self._create_signature(
            "app.tasks.delete_owner.DeleteOwner", kwargs=dict(ownerid=ownerid)
        ).apply_async()

    def backfill_repo(
        self,
        repository: Repository,
        start_date: datetime,
        end_date: datetime,
        dataset_names: Iterable[str] = None,
    ):
        log.info(
            "Triggering timeseries backfill tasks for repo",
            extra=dict(
                repoid=repository.pk,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                dataset_names=dataset_names,
            ),
        )

        # This controls the batch size for the task - we'll backfill
        # measurements 10 days at a time in this case.  I picked this
        # somewhat arbitrarily - we might need to tweak to see what's
        # most appropriate.
        delta = timedelta(days=10)

        signatures = []

        task_end_date = end_date
        while task_end_date > start_date:
            task_start_date = task_end_date - delta
            if task_start_date < start_date:
                task_start_date = start_date

            kwargs = dict(
                repoid=repository.pk,
                start_date=task_start_date.isoformat(),
                end_date=task_end_date.isoformat(),
            )
            if dataset_names is not None:
                kwargs["dataset_names"] = dataset_names

            signatures.append(
                self._create_signature(
                    celery_config.timeseries_backfill_task_name,
                    kwargs=kwargs,
                )
            )

            task_end_date = task_start_date

        group(signatures).apply_async()

    def backfill_dataset(
        self,
        dataset: Dataset,
        start_date: datetime,
        end_date: datetime,
    ):
        log.info(
            "Triggering dataset backfill",
            extra=dict(
                dataset_id=dataset.pk,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            ),
        )

        self._create_signature(
            "app.tasks.timeseries.backfill_dataset",
            kwargs=dict(
                dataset_id=dataset.pk,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            ),
        ).apply_async()

    def delete_timeseries(self, repository_id: int):
        log.info(
            "Delete repository timeseries data",
            extra=dict(repository_id=repository_id),
        )
        self._create_signature(
            celery_config.timeseries_delete_task_name,
            kwargs=dict(repository_id=repository_id),
        ).apply_async()

    def update_commit(self, commitid, repoid):
        self._create_signature(
            "app.tasks.commit_update.CommitUpdate",
            kwargs=dict(commitid=commitid, repoid=repoid),
        ).apply_async()

    def create_report_results(self, commitid, repoid, report_code, current_yaml=None):
        self._create_signature(
            "app.tasks.reports.save_report_results",
            kwargs=dict(
                commitid=commitid,
                repoid=repoid,
                report_code=report_code,
                current_yaml=current_yaml,
            ),
        ).apply_async()

    def http_request(self, url, method="POST", headers=None, data=None, timeout=None):
        self._create_signature(
            "app.tasks.http_request.HTTPRequest",
            kwargs=dict(
                url=url,
                method=method,
                headers=headers,
                data=data,
                timeout=timeout,
            ),
        ).apply_async()

    def flush_repo(self, repository_id: int):
        self._create_signature(
            "app.tasks.flush_repo.FlushRepo",
            kwargs=dict(repoid=repository_id),
        ).apply_async()

    def manual_upload_completion_trigger(
        self, repoid, commitid, report_code=None, current_yaml=None
    ):
        self._create_signature(
            "app.tasks.upload.ManualUploadCompletionTrigger",
            kwargs=dict(
                commitid=commitid,
                repoid=repoid,
                report_code=report_code,
                current_yaml=current_yaml,
            ),
        ).apply_async()

    def preprocess_upload(self, repoid, commitid, report_code):
        self._create_signature(
            "app.tasks.upload.PreProcessUpload",
            kwargs=dict(
                repoid=repoid,
                commitid=commitid,
                report_code=report_code,
            ),
        ).apply_async()

    def send_email(
        self,
        to_addr: str,
        subject: str,
        template_name: str,
        from_addr: str | None = None,
        **kwargs,
    ):
        # Templates can be found in worker/templates
        self._create_signature(
            "app.tasks.send_email.SendEmail",
            kwargs=dict(
                to_addr=to_addr,
                subject=subject,
                template_name=template_name,
                from_addr=from_addr,
                **kwargs,
            ),
        ).apply_async()

    def delete_component_measurements(self, repoid: int, component_id: str) -> None:
        log.info(
            "Delete component measurements data",
            extra=dict(repository_id=repoid, component_id=component_id),
        )
        self._create_signature(
            celery_config.timeseries_delete_task_name,
            kwargs=dict(
                repository_id=repoid,
                measurement_only=True,
                measurement_type=MeasurementName.COMPONENT_COVERAGE.value,
                measurement_id=component_id,
            ),
        ).apply_async()

    def cache_test_results_redis(self, repoid: int, branch: str) -> None:
        self._create_signature(
            celery_config.cache_test_rollups_redis_task_name,
            kwargs=dict(repoid=repoid, branch=branch),
        ).apply_async()
