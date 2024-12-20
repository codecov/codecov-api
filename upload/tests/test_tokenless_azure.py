from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from rest_framework.exceptions import NotFound

from upload.tokenless.azure import TokenlessAzureHandler


@pytest.fixture
def upload_params():
    return {
        "job": "899861",
        "project": "public",
        "server_uri": "https://dev.azure.com/dnceng-public/",
        "build": "20241219.14",
        "commit": "0f6e31fec5876be932f9e52f739ce1a2e04f11e3",
    }


def test_verify_handles_nanosecond_timestamp(upload_params):
    """
    Test that the handler correctly processes timestamps with nanosecond precision
    from the Azure DevOps API.
    """
    handler = TokenlessAzureHandler(upload_params)

    # Mock a response with nanosecond precision timestamp (7 digits after decimal)
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%S.1234567Z")

    mock_build_response = {
        "status": "completed",
        "finishTime": timestamp,
        "buildNumber": "20241219.14",
        "sourceVersion": "0f6e31fec5876be932f9e52f739ce1a2e04f11e3",
        "repository": {"type": "GitHub"},
    }

    with patch.object(handler, "get_build", return_value=mock_build_response):
        service = handler.verify()
        assert service == "github"


def test_verify_handles_microsecond_timestamp(upload_params):
    """
    Test that the handler still works correctly with regular microsecond precision
    timestamps.
    """
    handler = TokenlessAzureHandler(upload_params)

    # Mock a response with microsecond precision (6 digits after decimal)
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%S.123456Z")

    mock_build_response = {
        "status": "completed",
        "finishTime": timestamp,
        "buildNumber": "20241219.14",
        "sourceVersion": "0f6e31fec5876be932f9e52f739ce1a2e04f11e3",
        "repository": {"type": "GitHub"},
    }

    with patch.object(handler, "get_build", return_value=mock_build_response):
        service = handler.verify()
        assert service == "github"


def test_verify_rejects_old_timestamp(upload_params):
    """
    Test that the handler correctly rejects timestamps older than 4 minutes,
    even with nanosecond precision.
    """
    handler = TokenlessAzureHandler(upload_params)

    # Create a timestamp that's more than 4 minutes old
    old_time = datetime.now() - timedelta(minutes=5)
    timestamp = old_time.strftime("%Y-%m-%dT%H:%M:%S.1234567Z")

    mock_build_response = {
        "status": "completed",
        "finishTime": timestamp,
        "buildNumber": "20241219.14",
        "sourceVersion": "0f6e31fec5876be932f9e52f739ce1a2e04f11e3",
        "repository": {"type": "GitHub"},
    }

    with patch.object(handler, "get_build", return_value=mock_build_response):
        with pytest.raises(NotFound, match="Azure build has already finished"):
            handler.verify()
