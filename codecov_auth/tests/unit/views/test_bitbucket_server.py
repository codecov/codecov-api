from unittest.mock import patch

import pytest
from django.http.cookie import SimpleCookie
from django.urls import reverse
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.models import Owner
from codecov_auth.views.bitbucket_server import (
    BitbucketServer,
    BitbucketServerLoginView,
)
from utils.encryption import encryptor


def test_get_bbs_redirect(client, settings, mocker):
    client_request_mock = mocker.patch.object(
        BitbucketServer,
        "api",
        side_effect=lambda *args, **kwargs: dict(
            oauth_token="SomeToken", oauth_token_secret="SomeTokenSecret"
        ),
    )
    settings.BITBUCKET_SERVER_CLIENT_ID = "this-is-the-important-bit"
    settings.BITBUCKET_SERVER_URL = "https://my.bitbucketserver.com"
    url = reverse("bbs-login")
    res = client.get(url, SERVER_NAME="localhost:8000")

    assert res.status_code == 302
    assert (
        res.url
        == "https://my.bitbucketserver.com/plugins/servlet/oauth/authorize?oauth_token=SomeToken"
    )
    client_request_mock.assert_called_with(
        "POST", f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/request-token"
    )


def test_get_bbs_redirect_bitbucket_fails_to_get_request_token(
    client, settings, mocker
):
    def faulty_response(*args, **kwargs):
        # This is the error class that BitbucketServer.api generates
        raise TorngitClientGeneralError(500, "data data", "BBS unavailable")

    client_request_mock = mocker.patch.object(
        BitbucketServer,
        "api",
        side_effect=faulty_response,
    )
    settings.BITBUCKET_REDIRECT_URI = "http://localhost"
    settings.CODECOV_DASHBOARD_URL = "dashboard.value"
    settings.BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
    settings.BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
    with pytest.raises(TorngitClientGeneralError):
        res = client.get(reverse("bbs-login"), SERVER_NAME="localhost:8000")


def test_get_bbs_already_token(client, settings, mocker, db, mock_redis):
    settings.BITBUCKET_SERVER_CLIENT_ID = "this-is-the-important-bit"
    settings.BITBUCKET_SERVER_URL = "https://my.bitbucketserver.com"
    settings.BITBUCKET_SERVER_REDIRECT_URI = "http://localhost"
    settings.CODECOV_DASHBOARD_URL = "dashboard.value"
    settings.COOKIE_SECRET = "aaaaa"

    async def fake_list_teams():
        return []

    async def fake_api(method, url):
        if method == "POST" and (
            url.endswith("/plugins/servlet/oauth/access-token")
            or url.endswith("/plugins/servlet/oauth/request-token")
        ):
            return dict(oauth_token="SomeToken", oauth_token_secret="SomeTokenSecret")
        elif method == "GET" and url.endswith("/plugins/servlet/applinks/whoami"):
            return "ThiagoCodecov"
        elif method == "GET" and ("/users/ThiagoCodecov" in url):
            return dict(
                name="ThiagoCodecov", id=101, displayName="Thiago Codecov", active=True
            )

    mocker.patch.object(BitbucketServer, "list_teams", side_effect=fake_list_teams)
    client_request_mock = mocker.patch.object(
        BitbucketServer, "api", side_effect=fake_api
    )
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )

    url = reverse("bbs-login")
    client.cookies = SimpleCookie(
        {
            "_oauth_request_token": "test66me7mkczp7mmuzwc35k|YWRqTFVUVHZVcUduZVZ4cGN1aEpLRzhSVnJGdkw3c24="
        }
    )
    res = client.get(
        url,
        {"oauth_verifier": 8519288973, "oauth_token": "test1daxl4jnhegoh4"},
        SERVER_NAME="localhost:8000",
    )
    client_request_mock.assert_called()
    assert res.status_code == 302
    assert res.url == "dashboard.value/bbs"
    assert "_oauth_request_token" in res.cookies
    cookie = res.cookies["_oauth_request_token"]
    assert cookie.value == ""
    assert cookie.get("domain") == settings.COOKIES_DOMAIN
    owner = Owner.objects.get(username="ThiagoCodecov", service="bitbucket_server")
    assert encryptor.decode(owner.oauth_token) == "SomeToken:SomeTokenSecret"
