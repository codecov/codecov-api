from uuid import UUID

from django.urls import reverse
from shared.torngit import Gitlab
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.helpers import decode_token_from_cookie
from codecov_auth.models import Session


def _get_state_from_redis(mock_redis):
    key_redis = mock_redis.keys("*")[0].decode()
    return key_redis.replace("oauth-state-", "")


def test_get_gitlab_redirect(client, settings, mock_redis, mocker):
    mocker.patch(
        "codecov_auth.views.gitlab.uuid4",
        return_value=UUID("fbdf86c6c8d64ed1b814e80b33df85c9"),
    )
    settings.GITLAB_CLIENT_ID = (
        "testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
    )
    settings.GITLAB_CLIENT_SECRET = (
        "testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
    )
    settings.GITLAB_REDIRECT_URI = "http://localhost/login/gitlab"
    url = reverse("gitlab-login")
    res = client.get(url, SERVER_NAME="localhost:8000")
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://gitlab.com/oauth/authorize?response_type=code&client_id=testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth&redirect_uri=http%3A%2F%2Flocalhost%2Flogin%2Fgitlab&state={state}"
    )


def test_get_gitlab_already_with_code(client, mocker, db, settings, mock_redis):
    settings.GITLAB_CLIENT_ID = (
        "testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
    )
    settings.GITLAB_CLIENT_SECRET = (
        "testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
    )
    settings.COOKIES_DOMAIN = ".simple.site"

    async def helper_func(*args, **kwargs):
        return {
            "id": 3124507,
            "name": "Thiago Ramos",
            "username": "ThiagoCodecov",
            "state": "active",
            "access_token": "testp2twc8gxedplfn91tm4zn4r4ak2xgyr4ug96q86r2gr0re0143f20nuftka8",
            "token_type": "Bearer",
            "refresh_token": "testqyuk6z4s086jcvwoncxz8owl57o30qx1mhxlw3lgqliisujsiakh3ejq91tt",
            "scope": "api",
        }

    async def helper_list_teams_func(*args, **kwargs):
        return [
            {
                "email": "hello@codecov.io",
                "id": "8226205",
                "name": "Codecov",
                "username": "codecov",
            }
        ]

    mocker.patch.object(Gitlab, "get_authenticated_user", side_effect=helper_func)
    mocker.patch.object(Gitlab, "list_teams", side_effect=helper_list_teams_func)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    url = reverse("gitlab-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gl")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "gitlab-token" in res.cookies
    assert "gitlab-username" in res.cookies
    token_cookie = res.cookies["gitlab-token"]
    username_cookie = res.cookies["gitlab-username"]
    cookie_token = decode_token_from_cookie(settings.COOKIE_SECRET, token_cookie.value)
    assert username_cookie.value == "ThiagoCodecov"
    assert username_cookie.get("domain") == ".simple.site"
    assert token_cookie.get("domain") == ".simple.site"
    session = Session.objects.get(token=cookie_token)
    owner = session.owner
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "3124507"
    assert res.url == "http://localhost:3000/gl"


def test_get_github_already_with_code_github_error(
    client, mocker, db, mock_redis, settings
):
    settings.COOKIES_DOMAIN = ".simple.site"

    async def helper_func(*args, **kwargs):
        raise TorngitClientGeneralError(403, "response", "message")

    mocker.patch.object(Gitlab, "get_authenticated_user", side_effect=helper_func)
    url = reverse("gitlab-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gl")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "gitlab-token" not in res.cookies
    assert "gitlab-username" not in res.cookies
    assert res.url == "/"
