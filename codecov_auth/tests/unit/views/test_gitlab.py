from unittest.mock import call
from uuid import UUID

import pytest
from django.urls import reverse
from shared.torngit import Gitlab
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.models import Owner
from utils.encryption import encryptor


def _get_state_from_redis(mock_redis):
    key_redis = mock_redis.keys("*")[0].decode()
    return key_redis.replace("oauth-state-", "")


@pytest.mark.django_db
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
        == f"https://gitlab.com/oauth/authorize?response_type=code&client_id=testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth&redirect_uri=http%3A%2F%2Flocalhost%2Flogin%2Fgitlab&state={state}&scope=api"
    )


def test_get_gitlab_already_with_code(client, mocker, db, settings, mock_redis):
    settings.GITLAB_CLIENT_ID = (
        "testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
    )
    settings.GITLAB_CLIENT_SECRET = (
        "testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
    )
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "cookie-secret"

    access_token = "testp2twc8gxedplfn91tm4zn4r4ak2xgyr4ug96q86r2gr0re0143f20nuftka8"
    refresh_token = "testqyuk6z4s086jcvwoncxz8owl57o30qx1mhxlw3lgqliisujsiakh3ejq91tt"

    async def helper_func(*args, **kwargs):
        return {
            "id": 3124507,
            "name": "Thiago Ramos",
            "username": "ThiagoCodecov",
            "state": "active",
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
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

    session = client.session
    session["gitlab_oauth_state"] = "abc"
    session.save()
    mock_create_user_onboarding_metric = mocker.patch(
        "shared.django_apps.codecov_metrics.service.codecov_metrics.UserOnboardingMetricsService.create_user_onboarding_metric"
    )
    url = reverse("gitlab-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gl")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "3124507"
    assert res.url == "http://localhost:3000/gl"

    expected_call = call(
        org_id=owner.ownerid,
        event="INSTALLED_APP",
        payload={"login": "gitlab"},
    )
    assert mock_create_user_onboarding_metric.call_args_list == [expected_call]

    assert encryptor.decode(owner.oauth_token) == f"{access_token}: :{refresh_token}"


def test_get_gitlab_already_with_code_no_session(
    client, mocker, db, settings, mock_redis
):
    settings.GITLAB_CLIENT_ID = (
        "testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
    )
    settings.GITLAB_CLIENT_SECRET = (
        "testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
    )
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "cookie-secret"

    access_token = "testp2twc8gxedplfn91tm4zn4r4ak2xgyr4ug96q86r2gr0re0143f20nuftka8"
    refresh_token = "testqyuk6z4s086jcvwoncxz8owl57o30qx1mhxlw3lgqliisujsiakh3ejq91tt"

    async def helper_func(*args, **kwargs):
        return {
            "id": 3124507,
            "name": "Thiago Ramos",
            "username": "ThiagoCodecov",
            "state": "active",
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
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
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert res.url == "http://localhost:3000/gl"

    assert "current_owner_id" not in client.session


def test_get_github_already_with_code_gitlab_error(
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

    assert "current_owner_id" not in client.session
    assert res.url == "/"
