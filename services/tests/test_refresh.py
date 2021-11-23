from json import loads

import pytest

from services.refresh import RefreshService

celery_task_data = {"random": "data"}


class AsyncReturnMock:
    parent = None

    def as_tuple(self):
        return celery_task_data

    def successful(self):
        return False

    def failed(self):
        return False


class AsyncReturnMockSuccessful(AsyncReturnMock):
    def successful(self):
        return True


class AsyncReturnMockFailed(AsyncReturnMock):
    def failed(self):
        return True


class AsyncReturnMockParentFailed(AsyncReturnMock):
    @property
    def parent(self):
        return AsyncReturnMockFailed()


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


def test_refresh_makes_proper_redis_calls(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    assert mock_redis.get("refresh_5") == b'{"random": "data"}'


def test_dont_refresh_is_already_refreshing(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_refresh.assert_called()
    mock_refresh.reset_mock()
    RefreshService().trigger_refresh(5, "codecov")
    mock_refresh.assert_not_called()


def test_is_refreshing_false_when_task_is_successful(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    assert mock_redis.get("refresh_5") == b'{"random": "data"}'
    mock_result_from_tuple.return_value = AsyncReturnMockSuccessful()
    assert RefreshService().is_refreshing(5) is False
    assert mock_redis.get("refresh_5") is None


def test_is_refreshing_false_when_task_is_failed(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_result_from_tuple.return_value = AsyncReturnMockFailed()
    assert RefreshService().is_refreshing(5) is False


def test_is_refreshing_false_when_parent_task_is_failed(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_result_from_tuple.return_value = AsyncReturnMockParentFailed()
    assert RefreshService().is_refreshing(5) is False


def test_is_refreshing_false_when_result_from_tuple_raise(
    mock_result_from_tuple, mock_refresh, mock_redis
):
    RefreshService().trigger_refresh(5, "codecov")
    mock_result_from_tuple.side_effect = ValueError
    assert RefreshService().is_refreshing(5) is False
