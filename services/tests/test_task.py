from services.task import TaskService


def test_schedule_refresh_task(mocker):
    mocker.patch("celery_config.task_default_queue", "test_queue")
    ownerid = 5
    username = "codecov"
    task_service = TaskService()
    assert not task_service.is_refreshing(ownerid)
    task_service.refresh(ownerid, username)
    assert task_service.is_refreshing(ownerid)
    task_service.refresh(ownerid, username)
