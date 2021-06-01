import pytest
from services.refresh import RefreshService
from json import loads

celery_task_data = {"random": "data"}


class AsyncReturnMock:
    def as_tuple(self):
        return celery_task_data

    def ready(self):
        return False


class AsyncReturnMockFinished:
    def as_tuple(self):
        return celery_task_data

    def ready(self):
        return True


@pytest.fixture
def mock_refresh(mocker):
    mock_task_service = mocker.patch("services.task.TaskService.refresh")
    mock_task_service.return_value = AsyncReturnMock()
    yield mock_task_service


@pytest.fixture
def mock_result_from_tuple(mocker):
    mock_result_from_tuple = mocker.patch("services.refresh.result_from_tuple")
    mock_result_from_tuple.return_value = AsyncReturnMock()
    yield mock_result_from_tuple


def test_is_refreshing_true_after_trigger(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    assert RefreshService().is_refreshing(5) is False
    RefreshService().trigger_refresh(5, "codecov")
    assert RefreshService().is_refreshing(5) is True


def test_dont_refresh_is_already_refreshing(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_refresh.assert_called()
    mock_refresh.reset_mock()
    RefreshService().trigger_refresh(5, "codecov")
    mock_refresh.assert_not_called()


def test_is_refreshing_false_when_task_finish(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_result_from_tuple.return_value = AsyncReturnMockFinished()
    assert RefreshService().is_refreshing(5) is False
