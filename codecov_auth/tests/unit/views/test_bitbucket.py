from uuid import UUID
from django.http.cookie import SimpleCookie

from django.urls import reverse
from shared.torngit.bitbucket import Bitbucket


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
    print(res.url)
    assert "_oauth_request_token" in res.cookies
    cookie = res.cookies["_oauth_request_token"]
    assert (
        cookie.value
        == "Y3dVckVuQVY2S1pOVjhIOFE0|ZjRWNTY4TFc1OWc0Vkt3WjM5WDU1blFNSzVyc3FCVlk="
    )
    assert cookie.get("domain") == ""
    assert (
        res.url
        == "https://bitbucket.org/api/1.0/oauth/authenticate?oauth_token=testy6r2of6ajkmrub"
    )
    mocked_get.assert_called_with(settings.BITBUCKET_REDIRECT_URI)


def test_get_bitbucket_already_token(client, settings, mocker, db, mock_redis):
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
    assert res.url == "/bb"
    mocked_get.assert_called_with(
        "test1daxl4jnhegoh4", "adjLUTTvUqGneVxpcuhJKG8RVrFvL7sn", "8519288973"
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
