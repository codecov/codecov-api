import pytest
from django.conf import settings
from django.contrib import auth
from django.test import override_settings
from django.urls import reverse
from shared.django_apps.codecov_auth.tests.factories import (
    OktaUserFactory,
    OwnerFactory,
    UserFactory,
)

from codecov_auth.models import OktaUser
from codecov_auth.views.okta import OKTA_BASIC_AUTH
from codecov_auth.views.okta_mixin import OktaIdTokenPayload


@pytest.fixture
def mocked_okta_token_request(mocker):
    return mocker.patch(
        "codecov_auth.views.okta_mixin.requests.post",
        return_value=mocker.MagicMock(
            status_code=200,
            json=mocker.MagicMock(
                return_value={
                    "access_token": "test-access-token",
                    "refresh_token": "test-refresh-token",
                    "id_token": "test-id-token",
                    "state": "test-state",
                },
            ),
        ),
    )


@pytest.fixture
def mocked_validate_id_token(mocker):
    return mocker.patch(
        "codecov_auth.views.okta.validate_id_token",
        return_value=OktaIdTokenPayload(
            sub="test-id",
            email="test@example.com",
            name="Some User",
            iss="https://example.com",
            aud="test-client-id",
        ),
    )


# random keypair for RS256 JWTs used below
public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u
+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyeh
kd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ
0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdg
cKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbc
mwIDAQAB
-----END PUBLIC KEY-----
"""


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_redirect_to_authorize(client, db):
    res = client.get(
        reverse("okta-login"),
        data={
            "iss": "https://example.okta.com",
        },
    )
    state = client.session["okta_oauth_state"]

    assert res.status_code == 302
    assert (
        res.url
        == "https://example.okta.com/oauth2/v1/authorize?response_type=code&client_id=test-client-id&scope=openid+email+profile&redirect_uri=https%3A%2F%2Flocalhost%3A8000%2Flogin%2Fokta&state={}".format(
            state
        )
    )


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
    OKTA_ISS=None,
)
def test_okta_redirect_to_authorize_no_iss(client):
    res = client.get(reverse("okta-login"))
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
    OKTA_ISS="https://non.okta.domain",
)
def test_okta_redirect_to_authorize_invalid_iss(client):
    res = client.get(reverse("okta-login"))
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    mocked_okta_token_request.assert_called_once_with(
        "https://example.okta.com/oauth2/v1/token",
        auth=OKTA_BASIC_AUTH,
        data={
            "grant_type": "authorization_code",
            "code": "test-code",
            "redirect_uri": "https://localhost:8000/login/okta",
            "state": state,
        },
    )

    mocked_validate_id_token.assert_called_once_with(
        "https://example.okta.com", "test-id-token", "test-client-id"
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    okta_user = OktaUser.objects.get(okta_id="test-id")
    assert okta_user.access_token == "test-access-token"
    assert okta_user.email == "test@example.com"
    assert okta_user.name == "Some User"
    user = okta_user.user
    assert user is not None
    assert user.email == okta_user.email
    assert user.name == okta_user.name

    # logs in new user
    current_user = auth.get_user(client)
    assert user == current_user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_authenticated(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    user = UserFactory()
    client.force_login(user=user)

    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    okta_user = OktaUser.objects.get(okta_id="test-id")
    assert okta_user.access_token == "test-access-token"
    assert okta_user.email == "test@example.com"
    assert okta_user.name == "Some User"
    assert okta_user.user == user

    # leaves user logged in
    current_user = auth.get_user(client)
    assert user == current_user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_existing_okta_user(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    okta_user = OktaUserFactory(okta_id="test-id")

    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_authenticated_existing_okta_user(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    okta_user = OktaUserFactory(okta_id="test-id")
    other_okta_user = OktaUserFactory()

    client.force_login(user=other_okta_user.user)

    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
@pytest.mark.django_db
def test_okta_perform_login_existing_okta_user_existing_owner(
    client, mocked_okta_token_request, mocked_validate_id_token
):
    okta_user = OktaUserFactory(okta_id="test-id")
    OwnerFactory(service="github", user=okta_user.user)

    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    # redirects to service page
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/gh"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_error(client, mocker, db):
    mocker.patch(
        "codecov_auth.views.okta_mixin.requests.post",
        return_value=mocker.MagicMock(
            status_code=401,
        ),
    )
    state = "test-state"
    session = client.session
    session["okta_oauth_state"] = state
    session.save()

    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRET="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_state_mismatch(client, mocker, db):
    res = client.get(
        reverse("okta-login"),
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
