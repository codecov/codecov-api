import re
from datetime import datetime
from unittest.mock import call

import pytest
from django.http.cookie import SimpleCookie
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from shared.config import ConfigHelper
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import DEFAULT_FREE_PLAN
from shared.torngit import Github
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.models import Owner
from codecov_auth.views.github import GithubLoginView


def _get_state_from_redis(mock_redis):
    key_redis = mock_redis.keys("*")[0].decode()
    return key_redis.replace("oauth-state-", "")


@override_settings(GITHUB_CLIENT_ID="testclientid")
@pytest.mark.django_db
def test_get_github_redirect(client, mocker, mock_redis, settings):
    settings.IS_ENTERPRISE = False

    url = reverse("github-login")
    res = client.get(url)
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://github.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook&client_id=testclientid&state={state}"
    )


@override_settings(GITHUB_CLIENT_ID="testclientid")
@pytest.mark.django_db
def test_get_github_redirect_host_override(client, mocker, mock_redis, settings):
    settings.IS_ENTERPRISE = False
    config = ConfigHelper()
    gh_data = {"github": {"url": "https://fake.com", "host_override": "extrafake.com"}}

    def fake_config(*path, default=None):
        curr = config
        for key in path:
            if key in gh_data:
                curr = gh_data.get(key)
            elif key in curr:
                curr = curr.get(key)
            else:
                return default
        return curr

    mocker.patch(
        "shared.torngit.github.get_config",
        side_effect=fake_config,
    )
    url = reverse("github-login")
    res = client.get(url)
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://extrafake.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook&client_id=testclientid&state={state}"
    )


@override_settings(GITHUB_CLIENT_ID="testclientid")
@pytest.mark.django_db
def test_get_github_redirect_with_ghpr_cookie(client, mocker, mock_redis, settings):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"
    client.cookies = SimpleCookie({"ghpr": "true"})

    url = reverse("github-login")
    res = client.get(url)
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://github.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook%2Crepo&client_id=testclientid&state={state}"
    )
    assert "ghpr" in res.cookies
    ghpr_cooke = res.cookies["ghpr"]
    assert ghpr_cooke.value == "true"
    assert ghpr_cooke.get("domain") == ".simple.site"


@override_settings(GITHUB_CLIENT_ID="testclientid")
@pytest.mark.django_db
def test_get_github_redirect_with_private_url(client, mocker, mock_redis, settings):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    url = reverse("github-login")
    res = client.get(url, {"private": "true"})
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://github.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook%2Crepo&client_id=testclientid&state={state}"
    )
    assert "ghpr" in res.cookies
    ghpr_cooke = res.cookies["ghpr"]
    assert ghpr_cooke.value == "true"
    assert ghpr_cooke.get("domain") == ".simple.site"


def test_get_github_already_with_code(client, mocker, db, mock_redis, settings):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"
    now = datetime.now()
    now_tz = timezone.now()

    async def helper_func(*args, **kwargs):
        return {
            "login": "ThiagoCodecov",
            "id": 44376991,
            "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
            "avatar_url": "https://avatars3.githubusercontent.com/u/44376991?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/ThiagoCodecov",
            "html_url": "https://github.com/ThiagoCodecov",
            "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
            "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
            "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
            "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
            "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
            "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
            "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
            "type": "User",
            "site_admin": False,
            "name": "Thiago",
            "company": "@codecov ",
            "blog": "",
            "location": None,
            "email": None,
            "hireable": None,
            "bio": None,
            "twitter_username": None,
            "public_repos": 3,
            "public_gists": 0,
            "followers": 0,
            "following": 0,
            "created_at": "2018-10-22T17:51:44Z",
            "updated_at": "2020-10-14T17:58:13Z",
            "access_token": "test3k5zz19xqwhgr3eitwcm0lis74s9o0dlovnr",
            "token_type": "bearer",
            "scope": "read:org,repo:status,user:email,write:repo_hook,repo",
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

    async def is_student(*args, **kwargs):
        return False

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    mocker.patch.object(Github, "list_teams", side_effect=helper_list_teams_func)
    mocker.patch.object(Github, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )

    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()

    url = reverse("github-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "44376991"
    assert owner.email is None
    assert owner.private_access is True
    assert owner.service == "github"
    assert owner.name == "Thiago"
    assert owner.oauth_token is not None  # cannot test exact value
    assert owner.stripe_customer_id is None
    assert owner.stripe_subscription_id is None
    assert owner.createstamp > now_tz
    assert owner.service_id == "44376991"
    assert owner.parent_service_id is None
    assert owner.root_parent_service_id is None
    assert not owner.staff
    assert owner.cache is None
    assert owner.plan == DEFAULT_FREE_PLAN
    assert owner.plan_provider is None
    assert owner.plan_user_count == 1
    assert owner.plan_auto_activate is True
    assert owner.plan_activated_users is None
    assert owner.did_trial is None
    assert owner.free == 0
    assert owner.invoice_details is None
    assert owner.delinquent is None
    assert owner.yaml is None
    assert owner.updatestamp > now
    assert owner.admins is None
    assert owner.integration_id is None
    assert owner.permission is None
    assert owner.bot is None
    assert owner.student is False
    assert owner.student_created_at is None
    assert owner.student_updated_at is None
    # testing orgs
    assert owner.organizations is not None
    assert len(owner.organizations) == 1
    org = Owner.objects.get(ownerid=owner.organizations[0])
    assert org.service_id == "8226205"
    assert org.service == "github"
    assert res.url == "http://localhost:3000/gh"


def test_get_github_already_with_code_github_error(
    client, mocker, db, mock_redis, settings
):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    async def helper_func(*args, **kwargs):
        raise TorngitClientGeneralError(403, "response", "message")

    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    url = reverse("github-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    assert "current_owner_id" not in client.session
    assert res.url == "/"


def test_state_not_known(client, mocker, db, mock_redis, settings):
    url = reverse("github-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "doesnt exist"})
    assert res.status_code == 302
    assert "current_owner_id" not in client.session


@freeze_time("2023-02-01T00:00:00")
def test_get_github_already_with_code_with_email(
    client, mocker, db, mock_redis, settings
):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    async def helper_func(*args, **kwargs):
        return {
            "email": "thiago@codecov.io",
            "login": "ThiagoCodecov",
            "id": 44376991,
            "access_token": "testh04ph89fx0nkd3diauxcw75fyiuo3b86fw4j",
            "scope": "read:org,repo:status,user:email,write:repo_hook,repo",
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

    async def is_student(*args, **kwargs):
        return True

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    mocker.patch.object(Github, "list_teams", side_effect=helper_list_teams_func)
    mocker.patch.object(Github, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )

    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")
    url = reverse("github-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "44376991"
    assert owner.email == "thiago@codecov.io"
    assert owner.private_access is True
    assert res.url == "http://localhost:3000/gh"


@freeze_time("2023-01-01T00:00:00")
def test_get_github_already_with_code_is_student(
    client, mocker, db, mock_redis, settings
):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    async def helper_func(*args, **kwargs):
        return {
            "login": "ThiagoCodecov",
            "id": 44376991,
            "access_token": "testh04ph89fx0nkd3diauxcw75fyiuo3b86fw4j",
            "scope": "read:org,repo:status,user:email,write:repo_hook,repo",
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

    async def is_student(*args, **kwargs):
        return True

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    mocker.patch.object(Github, "list_teams", side_effect=helper_list_teams_func)
    mocker.patch.object(Github, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    mock_create_user_onboarding_metric = mocker.patch(
        "shared.django_apps.codecov_metrics.service.codecov_metrics.UserOnboardingMetricsService.create_user_onboarding_metric"
    )

    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")
    url = reverse("github-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    expected_call = call(
        org_id=client.session["current_owner_id"],
        event="INSTALLED_APP",
        payload={"login": "github"},
    )
    assert mock_create_user_onboarding_metric.call_args_list == [expected_call]

    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.email is None
    assert owner.service_id == "44376991"
    assert owner.private_access is True
    assert res.url == "http://localhost:3000/gh"
    assert owner.student is True


@freeze_time("2023-01-01T00:00:00")
def test_get_github_already_owner_already_exist(
    client, mocker, db, mock_redis, settings
):
    the_bot = OwnerFactory.create(service="github")
    the_bot.save()
    owner = OwnerFactory.create(bot=the_bot, service="github", service_id="44376991")
    owner.save()
    old_ownerid = owner.ownerid
    assert owner.bot is not None
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    async def helper_func(*args, **kwargs):
        return {
            "login": "ThiagoCodecov",
            "id": 44376991,
            "access_token": "testh04ph89fx0nkd3diauxcw75fyiuo3b86fw4j",
            "scope": "read:org,repo:status,user:email,write:repo_hook,repo",
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

    async def is_student(*args, **kwargs):
        return True

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    mocker.patch.object(Github, "list_teams", side_effect=helper_list_teams_func)
    mocker.patch.object(Github, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )

    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()

    url = reverse("github-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302

    owner = Owner.objects.get(pk=client.session["current_owner_id"])
    assert owner.username == "ThiagoCodecov"
    assert owner.ownerid == old_ownerid
    assert owner.bot is None
    assert owner.service_id == "44376991"
    assert owner.private_access is True
    assert res.url == "http://localhost:3000/gh"


@pytest.mark.asyncio
@override_settings(IS_ENTERPRISE=True)
async def test__get_teams_info(client, mocker):
    github = GithubLoginView()
    repo_service = Github()

    async def helper_api(*args):
        url: str = args[2]
        if url.startswith("/user/teams"):
            match = re.search(r"&page=(\d+)", url)
            page_number = match.group(1)
            if page_number == "1":
                return [dict(name="My team")]
            elif page_number == "2":
                return [dict(name="My team in another page")]
            return []
        return None

    mocker.patch.object(Github, "api", side_effect=helper_api)
    result = await github._get_teams_data(repo_service)
    assert result == [dict(name="My team"), dict(name="My team in another page")]


@pytest.mark.asyncio
@override_settings(IS_ENTERPRISE=True)
async def test__get_teams_info_fails(client, mocker):
    github = GithubLoginView()
    repo_service = Github()

    async def helper_api(*args):
        raise TorngitClientGeneralError(
            status_code=500,
            response_data=dict(error="generic error"),
            message="generic error",
        )

    mocker.patch.object(Github, "api", side_effect=helper_api)

    result = await github._get_teams_data(repo_service)
    assert result == []


def test_get_github_missing_access_token(client, mocker, db, mock_redis, settings):
    settings.COOKIES_DOMAIN = ".simple.site"
    settings.COOKIE_SECRET = "secret"

    async def helper_func(*args, **kwargs):
        return {
            "id": 44376991,
        }

    mocker.patch.object(Github, "get_authenticated_user", side_effect=helper_func)
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/gh")
    session = client.session
    session["github_oauth_state"] = "abc"
    session.save()
    url = reverse("github-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert res.headers["Location"] == "/"
