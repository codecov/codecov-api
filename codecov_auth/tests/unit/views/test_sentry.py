import pytest
from django.conf import settings
from django.contrib import auth
from django.test import override_settings
from django.urls import reverse

from codecov_auth.models import SentryUser
from codecov_auth.tests.factories import OwnerFactory, SentryUserFactory, UserFactory


@pytest.fixture
def mocked_sentry_request(mocker):
    return mocker.patch(
        "codecov_auth.views.sentry.requests.post",
        return_value=mocker.MagicMock(
            status_code=200,
            json=mocker.MagicMock(
                return_value={
                    "access_token": "test-access-token",
                    "refresh_token": "test-refresh-token",
                    "user": {
                        "id": "test-id",
                        "email": "test@example.com",
                        "name": "Some User",
                    },
                }
            ),
        ),
    )


@override_settings(SENTRY_OAUTH_CLIENT_ID="test-client-id")
def test_sentry_redirect_to_consent(client):
    res = client.get(reverse("sentry-login"))
    assert res.status_code == 302
    assert (
        res.url
        == "https://sentry.io/oauth/authorize?response_type=code&client_id=test-client-id&scope=openid+email+profile"
    )


def test_sentry_perform_login(client, mocked_sentry_request, db):
    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    mocked_sentry_request.assert_called_once_with(
        "https://sentry.io/oauth/token/",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SENTRY_OAUTH_CLIENT_ID,
            "client_secret": settings.SENTRY_OAUTH_CLIENT_SECRET,
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    sentry_user = SentryUser.objects.get(sentry_id="test-id")
    assert sentry_user.access_token == "test-access-token"
    assert sentry_user.refresh_token == "test-refresh-token"
    assert sentry_user.email == "test@example.com"
    assert sentry_user.name == "Some User"
    user = sentry_user.user
    assert user is not None
    assert user.email == sentry_user.email
    assert user.name == sentry_user.name

    # logs in new user
    current_user = auth.get_user(client)
    assert user == current_user


def test_sentry_perform_login_authenticated(client, mocked_sentry_request, db):
    user = UserFactory()
    client.force_login(user=user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    sentry_user = SentryUser.objects.get(sentry_id="test-id")
    assert sentry_user.access_token == "test-access-token"
    assert sentry_user.refresh_token == "test-refresh-token"
    assert sentry_user.email == "test@example.com"
    assert sentry_user.name == "Some User"
    assert sentry_user.user == user

    # leaves user logged in
    current_user = auth.get_user(client)
    assert user == current_user


def test_sentry_perform_login_existing_sentry_user(client, mocked_sentry_request, db):
    sentry_user = SentryUserFactory(sentry_id="test-id")

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


def test_sentry_perform_login_authenticated_existing_sentry_user(
    client, mocked_sentry_request, db
):
    sentry_user = SentryUserFactory(sentry_id="test-id")
    other_sentry_user = SentryUserFactory()
    client.force_login(user=other_sentry_user.user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


def test_sentry_perform_login_existing_sentry_user_existing_owner(
    client, mocked_sentry_request, db
):
    sentry_user = SentryUserFactory(sentry_id="test-id")
    OwnerFactory(service="github", user=sentry_user.user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    # redirects to service page
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/gh"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


def test_sentry_perform_login_error(client, mocker):
    mocker.patch(
        "codecov_auth.views.sentry.requests.post",
        return_value=mocker.MagicMock(
            status_code=401,
        ),
    )

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"
