from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.conf import settings
from django.contrib import auth
from django.test import override_settings
from django.urls import reverse
from shared.django_apps.codecov_auth.tests.factories import (
    OwnerFactory,
    SentryUserFactory,
    UserFactory,
)

from codecov_auth.models import SentryUser
from codecov_auth.views.sentry import SentryLoginView


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
                    "id_token": jwt.encode(
                        {
                            "iss": "https://sentry.io",
                            "aud": "test-client-id",
                        },
                        key="test-oidc-shared-secret",
                    ),
                }
            ),
        ),
    )


@override_settings(SENTRY_OAUTH_CLIENT_ID="test-client-id")
def test_sentry_redirect_to_consent(client, db):
    res = client.get(reverse("sentry-login"))
    state_from_session = client.session["sentry_oauth_state"]
    assert res.status_code == 302
    assert (
        res.url
        == "https://sentry.io/oauth/authorize?response_type=code&client_id=test-client-id&scope=openid+email+profile&state={}".format(
            state_from_session
        )
    )


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login(client, mocked_sentry_request, db):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    mocked_sentry_request.assert_called_once_with(
        "https://sentry.io/oauth/token/",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SENTRY_OAUTH_CLIENT_ID,
            "client_secret": settings.SENTRY_OAUTH_CLIENT_SECRET,
            "code": "test-code",
            "state": state,
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


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_authenticated(client, mocked_sentry_request, db):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    user = UserFactory()
    client.force_login(user=user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
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


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_existing_sentry_user(client, mocked_sentry_request, db):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    sentry_user = SentryUserFactory(sentry_id="test-id")

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_authenticated_existing_sentry_user(
    client, mocked_sentry_request, db
):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    sentry_user = SentryUserFactory(sentry_id="test-id")
    other_sentry_user = SentryUserFactory()
    client.force_login(user=other_sentry_user.user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_existing_sentry_user_existing_owner(
    client, mocked_sentry_request, db
):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    sentry_user = SentryUserFactory(sentry_id="test-id")
    OwnerFactory(service="github", user=sentry_user.user)

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    # redirects to service page
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/gh"

    # logs in sentry user
    current_user = auth.get_user(client)
    assert current_user == sentry_user.user


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_error(client, mocker, db):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

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
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="invalid-oidc-shared-secret",
)
def test_sentry_perform_login_invalid_id_token(client, mocked_sentry_request, db):
    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"

    # does not login user
    current_user = auth.get_user(client)
    assert current_user.is_anonymous


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_invalid_id_token_issuer(client, mocker, db):
    mocker.patch(
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
                    "id_token": jwt.encode(
                        {
                            "iss": "invalid-issuer",
                            "aud": "test-client-id",
                        },
                        key="test-oidc-shared-secret",
                    ),
                }
            ),
        ),
    )

    state = "test-state"
    session = client.session
    session["sentry_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"

    # does not login user
    current_user = auth.get_user(client)
    assert current_user.is_anonymous


@override_settings(
    SENTRY_OAUTH_CLIENT_ID="test-client-id",
    SENTRY_OIDC_SHARED_SECRET="test-oidc-shared-secret",
)
def test_sentry_perform_login_state_mismatch(client, mocked_sentry_request, db):
    res = client.get(
        reverse("sentry-login"),
        data={
            "code": "test-code",
            "state": "invalid-state",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"

    # does not login user
    current_user = auth.get_user(client)
    assert current_user.is_anonymous


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_sentry_fetch_user_data_invalid_state(client, db):
    with patch("codecov_auth.views.sentry.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.object(SentryLoginView, "verify_state", return_value=False):
            view = SentryLoginView()
            res = view._fetch_user_data(
                "test-code",
                "invalid-state",
            )

    assert res is None
