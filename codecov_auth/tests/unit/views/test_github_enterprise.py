from datetime import datetime
from unittest.mock import Mock, patch

from django.http.cookie import SimpleCookie
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from shared.torngit import GithubEnterprise
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.helpers import decode_token_from_cookie
from codecov_auth.models import Owner, Session
from codecov_auth.tests.factories import OwnerFactory


def _get_state_from_redis(mock_redis):
    key_redis = mock_redis.keys("*")[0].decode()
    return key_redis.replace("oauth-state-", "")


@override_settings(GITHUB_ENTERPRISE_CLIENT_ID="3d44be0e772666136a13")
def test_get_ghe_redirect(client, mocker, mock_redis):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    url = reverse("ghe-login")
    res = client.get(url)
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://my.githubenterprise.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook&client_id=3d44be0e772666136a13&state={state}"
    )
    mock_get_config.assert_called_with("github_enterprise", "url")


def test_get_ghe_redirect_with_ghpr_cookie(client, mocker, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    settings.COOKIES_DOMAIN = ".simple.site"
    client.cookies = SimpleCookie({"ghpr": "true"})
    url = reverse("ghe-login")
    res = client.get(url)
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://my.githubenterprise.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook%2Crepo&client_id=3d44be0e772666136a13&state={state}"
    )
    assert "ghpr" in res.cookies
    ghpr_cooke = res.cookies["ghpr"]
    assert ghpr_cooke.value == "true"
    assert ghpr_cooke.get("domain") == ".simple.site"


def test_get_github_redirect_with_private_url(client, mocker, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    settings.COOKIES_DOMAIN = ".simple.site"
    url = reverse("ghe-login")
    res = client.get(url, {"private": "true"})
    state = _get_state_from_redis(mock_redis)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://my.githubenterprise.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook%2Crepo&client_id=3d44be0e772666136a13&state={state}"
    )
    assert "ghpr" in res.cookies
    ghpr_cooke = res.cookies["ghpr"]
    assert ghpr_cooke.value == "true"
    assert ghpr_cooke.get("domain") == ".simple.site"


def test_get_ghe_already_with_code(client, mocker, db, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    settings.COOKIES_DOMAIN = ".simple.site"
    now = datetime.now()
    now_tz = timezone.now()

    async def helper_func(*args, **kwargs):
        return {
            "login": "ThiagoCodecov",
            "id": 44376991,
            "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
            "avatar_url": "https://avatars3.githubusercontent.com/u/44376991?v=4",
            "gravatar_id": "",
            "url": "https://api.githubenterprise.com/users/ThiagoCodecov",
            "html_url": "https://github.com/ThiagoCodecov",
            "followers_url": "https://api.githubenterprise.com/users/ThiagoCodecov/followers",
            "following_url": "https://api.githubenterprise.com/users/ThiagoCodecov/following{/other_user}",
            "gists_url": "https://api.githubenterprise.com/users/ThiagoCodecov/gists{/gist_id}",
            "starred_url": "https://api.githubenterprise.com/users/ThiagoCodecov/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.githubenterprise.com/users/ThiagoCodecov/subscriptions",
            "organizations_url": "https://api.githubenterprise.com/users/ThiagoCodecov/orgs",
            "repos_url": "https://api.githubenterprise.com/users/ThiagoCodecov/repos",
            "events_url": "https://api.githubenterprise.com/users/ThiagoCodecov/events{/privacy}",
            "received_events_url": "https://api.githubenterprise.com/users/ThiagoCodecov/received_events",
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

    mocker.patch.object(
        GithubEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    mocker.patch.object(
        GithubEnterprise, "list_teams", side_effect=helper_list_teams_func
    )
    mocker.patch.object(GithubEnterprise, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )

    url = reverse("ghe-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/ghe")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "github_enterprise-token" in res.cookies
    assert "github_enterprise-username" in res.cookies
    token_cookie = res.cookies["github_enterprise-token"]
    username_cookie = res.cookies["github_enterprise-username"]
    cookie_token = decode_token_from_cookie(settings.COOKIE_SECRET, token_cookie.value)
    assert username_cookie.value == "ThiagoCodecov"
    assert username_cookie.get("domain") == ".simple.site"
    assert token_cookie.get("domain") == ".simple.site"
    session = Session.objects.get(token=cookie_token)
    owner = session.owner
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "44376991"
    assert owner.email is None
    assert owner.private_access is True
    assert owner.service == "github_enterprise"
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
    assert owner.plan == "users-basic"
    assert owner.plan_provider is None
    assert owner.plan_user_count is 5
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
    assert org.service == "github_enterprise"
    assert res.url == "http://localhost:3000/ghe"


def test_get_ghe_already_with_code_github_error(
    client, mocker, db, mock_redis, settings
):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    settings.COOKIES_DOMAIN = ".simple.site"

    async def helper_func(*args, **kwargs):
        raise TorngitClientGeneralError(403, "response", "message")

    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/ghe")

    mocker.patch.object(
        GithubEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    url = reverse("ghe-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "github_enterprise-token" not in res.cookies
    assert "github_enterprise-username" not in res.cookies
    assert res.url == "/"


def test_state_not_known(client, mocker, db, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    url = reverse("ghe-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "doesnt exist"})
    assert res.status_code == 400
    assert "github_enterprise-token" not in res.cookies
    assert "github_enterprise-username" not in res.cookies


def test_get_ghe_already_with_code_with_email(client, mocker, db, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    settings.COOKIES_DOMAIN = ".simple.site"

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
        return False

    mocker.patch.object(
        GithubEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    mocker.patch.object(
        GithubEnterprise, "list_teams", side_effect=helper_list_teams_func
    )
    mocker.patch.object(GithubEnterprise, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/ghe")
    url = reverse("ghe-login")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "github_enterprise-token" in res.cookies
    assert "github_enterprise-username" in res.cookies
    token_cookie = res.cookies["github_enterprise-token"]
    username_cookie = res.cookies["github_enterprise-username"]
    cookie_token = decode_token_from_cookie(settings.COOKIE_SECRET, token_cookie.value)
    assert username_cookie.value == "ThiagoCodecov"
    assert username_cookie.get("domain") == ".simple.site"
    assert token_cookie.get("domain") == ".simple.site"
    session = Session.objects.get(token=cookie_token)
    owner = session.owner
    assert owner.username == "ThiagoCodecov"
    assert owner.service_id == "44376991"
    assert owner.email == "thiago@codecov.io"
    assert owner.private_access is True
    assert res.url == "http://localhost:3000/ghe"


def test_get_ghe_already_owner_already_exist(client, mocker, db, mock_redis, settings):
    mock_get_config = mocker.patch(
        "shared.torngit.github_enterprise.get_config",
        side_effect=lambda *args: "https://my.githubenterprise.com",
    )
    settings.GITHUB_ENTERPRISE_CLIENT_ID = "3d44be0e772666136a13"
    the_bot = OwnerFactory.create(service="github_enterprise")
    the_bot.save()
    owner = OwnerFactory.create(
        bot=the_bot, service="github_enterprise", service_id="44376991"
    )
    owner.save()
    old_ownerid = owner.ownerid
    assert owner.bot is not None
    settings.COOKIES_DOMAIN = ".simple.site"

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

    mocker.patch.object(
        GithubEnterprise, "get_authenticated_user", side_effect=helper_func
    )
    mocker.patch.object(
        GithubEnterprise, "list_teams", side_effect=helper_list_teams_func
    )
    mocker.patch.object(GithubEnterprise, "is_student", side_effect=is_student)
    mocker.patch(
        "services.task.TaskService.refresh",
        return_value=mocker.MagicMock(
            as_tuple=mocker.MagicMock(return_value=("a", "b"))
        ),
    )
    url = reverse("ghe-login")
    mock_redis.setex("oauth-state-abc", 300, "http://localhost:3000/ghe")
    res = client.get(url, {"code": "aaaaaaa", "state": "abc"})
    assert res.status_code == 302
    assert "github_enterprise-token" in res.cookies
    assert "github_enterprise-username" in res.cookies
    token_cookie = res.cookies["github_enterprise-token"]
    username_cookie = res.cookies["github_enterprise-username"]
    cookie_token = decode_token_from_cookie(settings.COOKIE_SECRET, token_cookie.value)
    assert username_cookie.value == "ThiagoCodecov"
    assert username_cookie.get("domain") == ".simple.site"
    assert token_cookie.get("domain") == ".simple.site"
    session = Session.objects.get(token=cookie_token)
    owner = session.owner
    assert owner.username == "ThiagoCodecov"
    assert owner.ownerid == old_ownerid
    assert owner.bot is None
    assert owner.service_id == "44376991"
    assert owner.private_access is True
    assert res.url == "http://localhost:3000/ghe"
