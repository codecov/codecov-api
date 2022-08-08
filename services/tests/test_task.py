from shared import celery_config

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

def test_update_commit_task(mocker):
    signature_mock = mocker.patch("services.task.signature")
    TaskService().update_commit(1,2)
    signature_mock.assert_called_with(
        "app.tasks.commit_update.CommitUpdate",
        args=None,
        kwargs=dict(commitid=1, repoid=2),
        app=celery_app,
    )