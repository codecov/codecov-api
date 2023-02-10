from datetime import datetime
from operator import xor
from unittest.mock import MagicMock

import pytest
from celery import Task
from django.conf import settings
from shared import celery_config

from core.tests.factories import RepositoryFactory
from services.task import TaskService, celery_app
from timeseries.tests.factories import DatasetFactory


def test_refresh_task(mocker):
    chain_mock = mocker.patch("services.task.task.chain")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "my_queue"}
    )
    TaskService().refresh(5, "codecov")
    chain_mock.assert_called()
    mock_route_task.assert_called()


def test_compute_comparison_task(mocker):
    signature_mock = mocker.patch("services.task.task.signature")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "my_queue"}
    )
    TaskService().compute_comparison(5)
    mock_route_task.assert_called_with(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=5),
        options={},
    )
    signature_mock.assert_called_with(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=5),
        app=celery_app,
        queue="my_queue",
    )


def test_compute_comparisons_task(mocker):
    signature_mock = mocker.patch("services.task.task.signature")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "my_queue"}
    )
    apply_async_mock = mocker.patch("celery.group.apply_async")
    TaskService().compute_comparisons([5, 10])
    mock_route_task.assert_called_with(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=5),
        options={},
    )
    assert signature_mock.call_count == 2
    signature_mock.assert_any_call(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=10),
        app=celery_app,
        queue="my_queue",
    )
    signature_mock.assert_any_call(
        celery_config.compute_comparison_task_name,
        args=None,
        kwargs=dict(comparison_id=5),
        app=celery_app,
        queue="my_queue",
    )
    apply_async_mock.assert_called_once_with()


@pytest.mark.django_db
def test_backfill_repo(mocker):
    signature_mock = mocker.patch("services.task.task.signature")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "celery"}
    )
    apply_async_mock = mocker.patch("celery.group.apply_async")

    repo = RepositoryFactory()
    TaskService().backfill_repo(
        repo,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 25),
        dataset_names=["testing"],
    )

    assert signature_mock.call_count == 3
    assert mock_route_task.call_count == 3
    mock_route_task.assert_any_call(
        celery_config.timeseries_backfill_task_name,
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-15T00:00:00",
            end_date="2022-01-25T00:00:00",
            dataset_names=["testing"],
        ),
        options={},
    )

    signature_mock.assert_any_call(
        celery_config.timeseries_backfill_task_name,
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-15T00:00:00",
            end_date="2022-01-25T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
        queue="celery",
    )
    signature_mock.assert_any_call(
        celery_config.timeseries_backfill_task_name,
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-05T00:00:00",
            end_date="2022-01-15T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
        queue="celery",
    )
    signature_mock.assert_any_call(
        celery_config.timeseries_backfill_task_name,
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2022-01-01T00:00:00",
            end_date="2022-01-05T00:00:00",
            dataset_names=["testing"],
        ),
        app=celery_app,
        queue="celery",
    )

    apply_async_mock.assert_called_once_with()


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
@pytest.mark.django_db(databases=["timeseries"])
def test_backfill_dataset(mocker):
    signature_mock = mocker.patch("services.task.task.signature")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "celery"}
    )
    signature = MagicMock()
    signature_mock.return_value = signature

    dataset = DatasetFactory()
    TaskService().backfill_dataset(
        dataset,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 8, 9),
    )

    signature_mock.assert_called_with(
        "app.tasks.timeseries.backfill_dataset",
        args=None,
        kwargs=dict(
            dataset_id=dataset.pk,
            start_date="2022-01-01T00:00:00",
            end_date="2022-08-09T00:00:00",
        ),
        app=celery_app,
        queue="celery",
    )
    signature.apply_async.assert_called_once_with()


def test_update_commit_task(mocker):
    signature_mock = mocker.patch("services.task.task.signature")
    mock_route_task = mocker.patch(
        "services.task.task.route_task", return_value={"queue": "celery"}
    )
    TaskService().update_commit(1, 2)
    mock_route_task.assert_called_with(
        celery_config.commit_update_task_name,
        args=None,
        kwargs=dict(commitid=1, repoid=2),
        options={},
    )
    signature_mock.assert_called_with(
        celery_config.commit_update_task_name,
        args=None,
        kwargs=dict(commitid=1, repoid=2),
        app=celery_app,
        queue="celery",
    )
