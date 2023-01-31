import shared.celery_config as shared_celery_config
from shared.billing import BillingPlan
from shared.celery_router import route_tasks_based_on_user_plan

from codecov_auth.models import Owner
from compare.models import CommitComparison
from core.models import Repository
from profiling.models import ProfilingCommit, ProfilingUpload


def _get_user_plan_from_ownerid(ownerid, *args, **kwargs) -> str:
    owner = Owner.objects.filter(ownerid=ownerid).first()
    if owner:
        return owner.plan
    return BillingPlan.users_basic.db_name


def _get_user_plan_from_repoid(repoid, *args, **kwargs) -> str:
    repo = Repository.objects.filter(repoid=repoid).first()
    if repo and repo.author:
        return repo.author.plan
    return BillingPlan.users_basic.db_name


def _get_user_plan_from_profiling_commit(profiling_id, *args, **kwargs) -> str:
    profiling_commit = ProfilingCommit.objects.filter(id=profiling_id).first()
    if (
        profiling_commit
        and profiling_commit.repository
        and profiling_commit.repository.author
    ):
        return profiling_commit.repository.author.plan
    return BillingPlan.users_basic.db_name


def _get_user_plan_from_profiling_upload(profiling_upload_id, *args, **kwargs) -> str:
    profiling_upload = ProfilingUpload.objects.filter(id=profiling_upload_id).first()
    if (
        profiling_upload
        and profiling_upload.profiling_commit
        and profiling_upload.profiling_commit.repository
        and profiling_upload.profiling_commit.repository.author
    ):
        return profiling_upload.profiling_commit.repository.author.plan
    return BillingPlan.users_basic.db_name


def _get_user_plan_from_comparison_id(comparison_id, *args, **kwargs) -> str:
    compare_commit = (
        CommitComparison.objects.filter(id=comparison_id)
        .select_related("compare_commit__repository__author")
        .first()
    )
    if (
        compare_commit
        and compare_commit.compare_commit
        and compare_commit.compare_commit.repository
        and compare_commit.compare_commit.repository.author
    ):
        return compare_commit.compare_commit.repository.author.plan
    return BillingPlan.users_basic.db_name


def _get_user_plan_from_task(task_name: str, task_kwargs: dict) -> str:
    owner_plan_lookup_funcs = {
        # from ownerid
        shared_celery_config.delete_owner_task_name: _get_user_plan_from_ownerid,
        shared_celery_config.sync_repos_task_name: _get_user_plan_from_ownerid,
        shared_celery_config.sync_teams_task_name: _get_user_plan_from_ownerid,
        # from repoid
        shared_celery_config.upload_task_name: _get_user_plan_from_repoid,
        shared_celery_config.notify_task_name: _get_user_plan_from_repoid,
        shared_celery_config.status_set_error_task_name: _get_user_plan_from_repoid,
        shared_celery_config.status_set_pending_task_name: _get_user_plan_from_repoid,
        shared_celery_config.pulls_task_name: _get_user_plan_from_repoid,
        # from profiling_commitid
        shared_celery_config.profiling_collection_task_name: _get_user_plan_from_profiling_commit,
        # from profiling_upload_id
        shared_celery_config.profiling_normalization_task_name: _get_user_plan_from_profiling_upload,
        # from comparison_id
        shared_celery_config.compute_comparison_task_name: _get_user_plan_from_comparison_id,
    }
    func_to_use = owner_plan_lookup_funcs.get(
        task_name, lambda *args, **kwargs: BillingPlan.users_basic.db_name
    )
    return func_to_use(**task_kwargs)


def route_task(name, args, kwargs, options, task=None, **kw):
    """Function to dynamically route tasks to the proper queue.
    Docs: https://docs.celeryq.dev/en/stable/userguide/routing.html#routers
    """
    user_plan = _get_user_plan_from_task(name, kwargs)
    return route_tasks_based_on_user_plan(name, user_plan)
