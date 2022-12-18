import pytest
import shared.celery_config as shared_celery_config
from shared.billing import BillingPlan

from codecov_auth.tests.factories import OwnerFactory
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import RepositoryFactory
from profiling.models import ProfilingUpload
from profiling.tests.factories import ProfilingCommitFactory
from services.task.task_router import (
    _get_user_plan_from_comparison_id,
    _get_user_plan_from_ownerid,
    _get_user_plan_from_profiling_commit,
    _get_user_plan_from_profiling_upload,
    _get_user_plan_from_repoid,
    _get_user_plan_from_task,
    route_task,
)


@pytest.fixture
def fake_owners(db):
    owner = OwnerFactory.create(plan=BillingPlan.pr_monthly.db_name)
    owner_enterprise_cloud = OwnerFactory.create(
        plan=BillingPlan.enterprise_cloud_yearly.db_name
    )
    owner.save()
    owner_enterprise_cloud.save()
    return (owner, owner_enterprise_cloud)


@pytest.fixture
def fake_repos(db, fake_owners):
    (owner, owner_enterprise_cloud) = fake_owners

    repo = RepositoryFactory(author=owner)
    repo_enterprise = RepositoryFactory(author=owner_enterprise_cloud)
    repo.save()
    repo_enterprise.save()
    return (repo, repo_enterprise)


@pytest.fixture
def fake_profiling_commit(db, fake_repos):
    (repo, repo_enterprise) = fake_repos
    profiling_commit = ProfilingCommitFactory(repository=repo)
    profiling_commit_enterprise = ProfilingCommitFactory(repository=repo_enterprise)
    profiling_commit.save()
    profiling_commit_enterprise.save()
    return (profiling_commit, profiling_commit_enterprise)


@pytest.fixture
def fake_profiling_upload(db, fake_profiling_commit):
    (profing_commit, profiling_commit_enterprise) = fake_profiling_commit
    profiling_upload = ProfilingUpload(profiling_commit=profing_commit)
    profiling_upload_enterprise = ProfilingUpload(
        profiling_commit=profiling_commit_enterprise
    )
    profiling_upload.save()
    profiling_upload_enterprise.save()
    return (profiling_upload, profiling_upload_enterprise)


@pytest.fixture
def fake_compare_commit(db, fake_repos):
    (repo, repo_enterprise) = fake_repos
    compare_commit = CommitComparisonFactory(compare_commit__repository=repo)
    compare_commit_enterprise = CommitComparisonFactory(
        compare_commit__repository=repo_enterprise
    )
    compare_commit.save()
    compare_commit_enterprise.save()
    return (compare_commit, compare_commit_enterprise)


def test_get_owner_plan_from_ownerid(fake_owners):
    (owner, owner_enterprise_cloud) = fake_owners
    assert _get_user_plan_from_ownerid(owner.ownerid) == BillingPlan.pr_monthly.db_name
    assert (
        _get_user_plan_from_ownerid(owner_enterprise_cloud.ownerid)
        == BillingPlan.enterprise_cloud_yearly.db_name
    )
    assert _get_user_plan_from_ownerid(10000000) == BillingPlan.users_basic.db_name


def test_get_owner_plan_from_repoid(fake_repos):
    (repo, repo_enterprise) = fake_repos
    assert _get_user_plan_from_repoid(repo.repoid) == BillingPlan.pr_monthly.db_name
    assert (
        _get_user_plan_from_repoid(repo_enterprise.repoid)
        == BillingPlan.enterprise_cloud_yearly.db_name
    )
    assert _get_user_plan_from_repoid(10000000) == BillingPlan.users_basic.db_name


def test_get_owner_plan_from_profiling_id(fake_profiling_commit):
    (profing_commit, profiling_commit_enterprise) = fake_profiling_commit
    assert (
        _get_user_plan_from_profiling_commit(profiling_id=profing_commit.id)
        == BillingPlan.pr_monthly.db_name
    )
    assert (
        _get_user_plan_from_profiling_commit(
            profiling_id=profiling_commit_enterprise.id
        )
        == BillingPlan.enterprise_cloud_yearly.db_name
    )
    assert (
        _get_user_plan_from_profiling_commit(10000000)
        == BillingPlan.users_basic.db_name
    )


def test_get_owner_plan_from_profiling_upload(fake_profiling_upload):
    (profiling_upload, profiling_upload_enterprise) = fake_profiling_upload
    assert (
        _get_user_plan_from_profiling_upload(profiling_upload.id)
        == BillingPlan.pr_monthly.db_name
    )
    assert (
        _get_user_plan_from_profiling_upload(profiling_upload_enterprise.id)
        == BillingPlan.enterprise_cloud_yearly.db_name
    )
    assert (
        _get_user_plan_from_profiling_upload(10000000)
        == BillingPlan.users_basic.db_name
    )


def test_get_user_plan_from_comparison_id(fake_compare_commit):
    (compare_commit, compare_commit_enterprise) = fake_compare_commit
    assert (
        _get_user_plan_from_comparison_id(compare_commit.id)
        == BillingPlan.pr_monthly.db_name
    )
    assert (
        _get_user_plan_from_comparison_id(compare_commit_enterprise.id)
        == BillingPlan.enterprise_cloud_yearly.db_name
    )
    assert (
        _get_user_plan_from_comparison_id(10000000) == BillingPlan.users_basic.db_name
    )


def test_get_user_plan_from_task(
    fake_repos,
    fake_profiling_commit,
    fake_profiling_upload,
    fake_compare_commit,
):
    (repo, repo_enterprise_cloud) = fake_repos
    profiling_commit = fake_profiling_commit[0]
    profiling_upload = fake_profiling_upload[0]
    compare_commit = fake_compare_commit[0]
    task_kwargs = dict(repoid=repo.repoid, commitid=0, debug=False, rebuild=False)
    assert (
        _get_user_plan_from_task(shared_celery_config.upload_task_name, task_kwargs)
        == BillingPlan.pr_monthly.db_name
    )

    task_kwargs = dict(
        repoid=repo_enterprise_cloud.repoid, commitid=0, debug=False, rebuild=False
    )
    assert (
        _get_user_plan_from_task(shared_celery_config.upload_task_name, task_kwargs)
        == BillingPlan.enterprise_cloud_yearly.db_name
    )

    task_kwargs = dict(ownerid=repo.author.ownerid)
    assert (
        _get_user_plan_from_task(
            shared_celery_config.delete_owner_task_name, task_kwargs
        )
        == BillingPlan.pr_monthly.db_name
    )

    task_kwargs = dict(profiling_id=profiling_commit.id)
    assert (
        _get_user_plan_from_task(
            shared_celery_config.profiling_collection_task_name, task_kwargs
        )
        == BillingPlan.pr_monthly.db_name
    )

    task_kwargs = dict(profiling_upload_id=profiling_upload.id)
    assert (
        _get_user_plan_from_task(
            shared_celery_config.profiling_normalization_task_name,
            task_kwargs,
        )
        == BillingPlan.pr_monthly.db_name
    )

    task_kwargs = dict(comparison_id=compare_commit.id)
    assert (
        _get_user_plan_from_task(
            shared_celery_config.compute_comparison_task_name, task_kwargs
        )
        == BillingPlan.pr_monthly.db_name
    )

    task_kwargs = dict(
        repoid=repo_enterprise_cloud.repoid, commitid=0, debug=False, rebuild=False
    )
    assert (
        _get_user_plan_from_task("unknown task", task_kwargs)
        == BillingPlan.users_basic.db_name
    )


def test_route_task(mocker, fake_repos):
    mock_route_tasks_shared = mocker.patch(
        "services.task.task_router.route_tasks_based_on_user_plan"
    )
    mock_route_tasks_shared.return_value = {"queue": "correct queue"}
    repo = fake_repos[0]
    task_kwargs = dict(repoid=repo.repoid, commitid=0, debug=False, rebuild=False)
    response = route_task(shared_celery_config.upload_task_name, [], task_kwargs, {})
    assert response == {"queue": "correct queue"}
    mock_route_tasks_shared.assert_called_with(
        shared_celery_config.upload_task_name, BillingPlan.pr_monthly.db_name
    )
