from unittest.mock import patch

from django.http.cookie import SimpleCookie
from django.test import TestCase
from django.urls import reverse
from shared.torngit.bitbucket import Bitbucket
from shared.torngit.exceptions import TorngitServer5xxCodeError

from codecov_auth.models import Owner
from codecov_auth.views.bitbucket import BitbucketLoginView
from utils.encryption import encryptor


def test_get_bitbucket_redirect(client, settings, mocker):
    mocked_get = mocker.patch.object(
        Bitbucket,
        "generate_request_token",
        return_value={
            "oauth_token": "testy6r2of6ajkmrub",
            "oauth_token_secret": "testzibw5q01scpl8qeeupzh8u9yu8hz",
        },
    )
    settings.BITBUCKET_REDIRECT_URI = "http://localhost"
    settings.BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
    settings.BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
    url = reverse("bitbucket-login")
    res = client.get(url, SERVER_NAME="localhost:8000")
    assert res.status_code == 302
    assert "_oauth_request_token" in res.cookies
    cookie = res.cookies["_oauth_request_token"]
    assert (
        cookie.value
        == "Y3dVckVuQVY2S1pOVjhIOFE0|ZjRWNTY4TFc1OWc0Vkt3WjM5WDU1blFNSzVyc3FCVlk="
    )
    assert cookie.get("domain") == settings.COOKIES_DOMAIN
    assert (
        res.url
        == "https://bitbucket.org/api/1.0/oauth/authenticate?oauth_token=testy6r2of6ajkmrub"
    )
    mocked_get.assert_called_with(settings.BITBUCKET_REDIRECT_URI)


def test_get_bitbucket_redirect_bitbucket_unavailable(client, settings, mocker):
    mocked_get = mocker.patch.object(
        Bitbucket, "generate_request_token", side_effect=TorngitServer5xxCodeError(),
    )
    settings.BITBUCKET_REDIRECT_URI = "http://localhost"
    settings.BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
    settings.BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
    url = reverse("bitbucket-login")
    res = client.get(url, SERVER_NAME="localhost:8000")
    assert res.status_code == 302
    assert "_oauth_request_token" not in res.cookies
    assert res.url == url
    mocked_get.assert_called_with(settings.BITBUCKET_REDIRECT_URI)


async def fake_get_authenticated_user():
    return {
        "username": "ThiagoCodecov",
        "has_2fa_enabled": None,
        "display_name": "Thiago Ramos",
        "account_id": "5bce04c759d0e84f8c7555e9",
        "links": {
            "hooks": {
                "href": "https://bitbucket.org/!api/2.0/users/%7B9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645%7D/hooks"
            },
            "self": {
                "href": "https://bitbucket.org/!api/2.0/users/%7B9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645%7D"
            },
            "repositories": {
                "href": "https://bitbucket.org/!api/2.0/repositories/%7B9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645%7D"
            },
            "html": {
                "href": "https://bitbucket.org/%7B9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645%7D/"
            },
            "avatar": {
                "href": "https://avatar-management--avatars.us-west-2.prod.public.atl-paas.net/initials/TR-6.png"
            },
            "snippets": {
                "href": "https://bitbucket.org/!api/2.0/snippets/%7B9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645%7D"
            },
        },
        "nickname": "thiago",
        "created_on": "2018-11-06T12:12:59.588751+00:00",
        "is_staff": False,
        "location": None,
        "account_status": "active",
        "type": "user",
        "uuid": "{9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645}",
    }


def test_get_bitbucket_already_token(client, settings, mocker, db, mock_redis):
    mocker.patch.object(
        Bitbucket, "get_authenticated_user", side_effect=fake_get_authenticated_user
    )

    async def fake_list_teams():
        return []

    mocker.patch.object(Bitbucket, "list_teams", side_effect=fake_list_teams)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    mocked_get = mocker.patch.object(
        Bitbucket,
        "generate_access_token",
        return_value={
            "key": "test6tl3evq7c8vuyn",
            "secret": "testdm61tppb5x0tam7nae3qajhcepzz",
        },
    )
    settings.BITBUCKET_REDIRECT_URI = "http://localhost"
    settings.BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
    settings.BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
    settings.CODECOV_DASHBOARD_URL = "dashboard.value"
    settings.COOKIE_SECRET = "aaaaa"
    url = reverse("bitbucket-login")
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
    assert res.status_code == 302
    assert res.url == "dashboard.value/bb"
    assert "_oauth_request_token" in res.cookies
    cookie = res.cookies["_oauth_request_token"]
    assert cookie.value == ""
    assert cookie.get("domain") == settings.COOKIES_DOMAIN
    mocked_get.assert_called_with(
        "test1daxl4jnhegoh4", "adjLUTTvUqGneVxpcuhJKG8RVrFvL7sn", "8519288973"
    )
    owner = Owner.objects.get(username="ThiagoCodecov", service="bitbucket")
    assert (
        encryptor.decode(owner.oauth_token)
        == "test6tl3evq7c8vuyn:testdm61tppb5x0tam7nae3qajhcepzz"
    )


def test_get_bitbucket_already_token_no_cookie(
    client, settings, mocker, db, mock_redis
):
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    mocked_get = mocker.patch.object(
        Bitbucket,
        "generate_access_token",
        return_value={
            "key": "test6tl3evq7c8vuyn",
            "secret": "testdm61tppb5x0tam7nae3qajhcepzz",
        },
    )
    settings.BITBUCKET_REDIRECT_URI = "http://localhost"
    settings.BITBUCKET_CLIENT_ID = "testqmo19ebdkseoby"
    settings.BITBUCKET_CLIENT_SECRET = "testfi8hzehvz453qj8mhv21ca4rf83f"
    url = reverse("bitbucket-login")
    res = client.get(
        url,
        {"oauth_verifier": 8519288973, "oauth_token": "test1daxl4jnhegoh4"},
        SERVER_NAME="localhost:8000",
    )
    assert res.status_code == 302
    assert res.url == "/login/bitbucket"
    assert not mocked_get.called


class TestBitbucketLoginView(TestCase):
    def test_fetch_user_data(self):
        async def fake_list_teams():
            return []

        with patch.object(
            Bitbucket, "get_authenticated_user", side_effect=fake_get_authenticated_user
        ):
            with patch.object(Bitbucket, "list_teams", side_effect=fake_list_teams):
                view = BitbucketLoginView()
                token = {"key": "aaaa", "secret": "bbbb"}
                res = view.fetch_user_data(token)
                assert res == {
                    "has_private_access": False,
                    "is_student": False,
                    "orgs": [],
                    "user": {
                        "access_token": "aaaa:bbbb",
                        "id": "9a01f37b-b1b2-40c5-8c5e-1a39f4b5e645",
                        "login": "ThiagoCodecov",
                    },
                }
