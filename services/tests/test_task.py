from datetime import datetime

import pytest
from celery import Task
from shared import celery_config

from core.tests.factories import RepositoryFactory
from services.task import TaskService, celery_app


def test_refresh_task(mocker):
    chain_mock = mocker.patch("services.task.chain")
    TaskService().refresh(5, "codecov")
    chain_mock.assert_called()


def test_compute_comparison_task(mocker):
    signature_mock = mocker.patch("services.task.signature")
    TaskService().compute_comparison(5)
    signature_mock.assert_called_with(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=5),
        app=celery_app,
    )


@pytest.mark.django_db
def test_backfill_repo(mocker):
    signature_mock = mocker.patch("services.task.signature")
    apply_async_mock = mocker.patch("celery.group.apply_async")

    repo = RepositoryFactory()
    TaskService().backfill_repo(
        repo,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 25),
        dataset_names=["testing"],
    )

    assert signature_mock.call_count == 3
    signature_mock.assert_any_call(
        "app.tasks.timeseries.backfill",
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-15T00:00:00",
            end_date="2022-01-25T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
    )
    signature_mock.assert_any_call(
        "app.tasks.timeseries.backfill",
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-05T00:00:00",
            end_date="2022-01-15T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
    )
    signature_mock.assert_any_call(
        "app.tasks.timeseries.backfill",
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-01T00:00:00",
            end_date="2022-01-05T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
    )

    apply_async_mock.assert_called_once_with()
