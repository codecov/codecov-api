from services.task import TaskService

from services.redis_configuration import get_redis_connection


def setup():
    get_redis_connection().flushdb()


def test_schedule_refresh_task():
    ownerid = 5
    username = "codecov"
    task_service = TaskService(queue="testing")
    assert task_service.is_refreshing(ownerid) == False
    task_service.refresh(ownerid, username)
    assert task_service.is_refreshing(ownerid) == True
