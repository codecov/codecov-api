from uuid import UUID

import pytest
from django.test import override_settings
from django.urls import reverse
from shared.torngit import GitlabEnterprise
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.models import Owner


def _get_state_from_redis(mock_redis):
    key_redis = mock_redis.keys("*")[0].decode()
    return key_redis.replace("oauth-state-", "")


@override_settings(
    GITLAB_ENTERPRISE_CLIENT_ID="testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
)
@override_settings(
    GITLAB_ENTERPRISE_CLIENT_SECRET="testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
)
@override_settings(GITLAB_ENTERPRISE_REDIRECT_URI="http://localhost/login/gle")
@pytest.mark.django_db
def test_get_gle_redirect(client, settings, mock_redis, mocker):
    mock_get_config = mocker.patch(
        "shared.torngit.gitlab_enterprise.get_config",
        side_effect=lambda *args: "https://my.gitlabenterprise.com",
    )
    mocker.patch(
        "codecov_auth.views.gitlab.uuid4",
        return_value=UUID("fbdf86c6c8d64ed1b814e80b33df85c9"),
    )
    url = reverse("gle-login")
    res = client.get(url, SERVER_NAME="localhost:8000")
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://my.gitlabenterprise.com/oauth/authorize?response_type=code&client_id=testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth&redirect_uri=http%3A%2F%2Flocalhost%2Flogin%2Fgle&state={state}&scope=api"
    )
    mock_get_config.assert_called_with("gitlab_enterprise", "url")


@override_settings(
    GITLAB_ENTERPRISE_CLIENT_ID="testfiuozujcfo5kxgigugr5x3xxx2ukgyandp16x6w566uits7f32crzl4yvmth"
)
@override_settings(
    GITLAB_ENTERPRISE_CLIENT_SECRET="testi1iinnfrhnf2q6htycgexmp04f1z2mrd7w7u8bigskhwq2km6yls8e2mddzh"
)
@override_settings(GITLAB_ENTERPRISE_REDIRECT_URI="http://localhost/login/gle")
def test_get_gle_already_with_code(client, mocker, db, settings, mock_redis):
    settings.COOKIE_SECRET = "secret"
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

    mocker.patch.object(
        GitlabEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    mocker.patch.object(
        GitlabEnterprise, "list_teams", side_effect=helper_list_teams_func
    )
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    url = reverse("gle-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gle")
    session = client.session
    session["gitlab_enterprise_oauth_state"] = "abc"
    session.save()
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "3124507"
    assert res.url == "http://localhost:3000/gle"


def test_get_gle_already_with_code_github_error(
    client, mocker, db, mock_redis, settings
):
    settings.COOKIES_DOMAIN = ".simple.site"

    async def helper_func(*args, **kwargs):
        raise TorngitClientGeneralError(403, "response", "message")

    mocker.patch.object(
        GitlabEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    url = reverse("gle-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gle")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "gitlab_enterprise-token" not in res.cookies
    assert "gitlab_enterprise-username" not in res.cookies
    assert res.url == "/"
