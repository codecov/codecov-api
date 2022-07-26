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
    repo = RepositoryFactory()
    TaskService().backfill_repo(repo, datetime(2020, 1, 1), datetime(2022, 1, 1))
    signature_mock.assert_called_with(
        "app.tasks.timeseries.backfill",
        args=None,
        kwargs=dict(
            repoid=repo.pk,
            start_date="2020-01-01T00:00:00",
            end_date="2022-01-01T00:00:00",
        ),
        app=celery_app,
    )
