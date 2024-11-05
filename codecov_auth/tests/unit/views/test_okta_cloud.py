from logging import LogRecord
from typing import Any
from unittest.mock import ANY
from urllib.parse import unquote, urlparse

import pytest
from django.test import override_settings
from pytest import LogCaptureFixture
from pytest_mock import MockerFixture
from shared.django_apps.codecov_auth.models import Account, OktaSettings, Owner
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    OktaSettingsFactory,
)
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov_auth.views.okta_cloud import (
    OKTA_CURRENT_SESSION,
    OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY,
)
from codecov_auth.views.okta_mixin import OktaIdTokenPayload
from utils.test_utils import Client as TestClient


@pytest.fixture
def signed_in_client() -> TestClient:
    new_client = TestClient()
    new_client.force_login_owner(OwnerFactory())
    return new_client


@pytest.fixture
def okta_org_name() -> str:
    return "foo-bar-organization"


@pytest.fixture
def okta_org(okta_org_name: str) -> Owner:
    org: Owner = OwnerFactory.create(username=okta_org_name, service="github")
    org.save()
    return org


@pytest.fixture
def okta_account(okta_org: Owner):
    account = AccountFactory()
    okta_org.account = account
    okta_org.save()

    okta_settings: OktaSettings = OktaSettingsFactory(account=account)
    okta_settings.url = "https://foo-bar.okta.com/"
    okta_settings.save()
    return account


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
        "codecov_auth.views.okta_cloud.validate_id_token",
        return_value=OktaIdTokenPayload(
            sub="test-id",
            email="test@example.com",
            name="Some User",
            iss="https://example.com",
            aud="test-client-id",
        ),
    )


def log_message_exists(message: str, logs: list[LogRecord]) -> bool:
    """Helper method to check that a particular log record was emitted"""
    for log in logs:
        if log.message == message:
            return True
    return False


@pytest.mark.django_db
def test_okta_login_unauthenticated_user(
    client: TestClient,
    caplog: LogCaptureFixture,
):
    res = client.get("/login/okta/github/some-unknown-service")
    assert log_message_exists(
        "User needs to be signed in before authenticating organization with Okta.",
        caplog.records,
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_okta_login_invalid_organization(
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
):
    res = signed_in_client.get("/login/okta/github/some-unknown-service")
    assert log_message_exists("The organization doesn't exist.", caplog.records)
    assert res.status_code == 404


@pytest.mark.django_db
def test_okta_login_no_account(signed_in_client: TestClient, caplog: LogCaptureFixture):
    org: Owner = OwnerFactory.create(username="org-no-account", service="github")
    org.save()
    res = signed_in_client.get("/login/okta/github/org-no-account")
    assert log_message_exists(
        "Okta settings not found. Cannot sign into Okta", caplog.records
    )
    assert res.status_code == 404


@pytest.mark.django_db
def test_okta_login_no_okta_settings(
    signed_in_client: TestClient, caplog: LogCaptureFixture
):
    org: Owner = OwnerFactory.create(username="account-no-okta", service="github")
    org.account = AccountFactory()
    org.save()
    res = signed_in_client.get("/login/okta/github/account-no-okta")
    assert log_message_exists(
        "Okta settings not found. Cannot sign into Okta", caplog.records
    )
    assert res.status_code == 404


@pytest.mark.django_db
def test_okta_login_already_signed_into_okta(
    signed_in_client: TestClient,
    okta_org_name: str,
    okta_account: Account,
):
    session = signed_in_client.session
    session[OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY] = [okta_account.id]
    session.save()
    res = signed_in_client.get(f"/login/okta/gh/{okta_org_name}")
    assert res.status_code == 302
    assert res.url == f"http://localhost:3000/github/{okta_org_name}"


@override_settings(
    CODECOV_API_URL="http://localhost:8000",
)
@pytest.mark.django_db
def test_okta_login_redirect_to_okta_issuer(
    signed_in_client: TestClient, okta_org_name: str, okta_account: Account
):
    res = signed_in_client.get(f"/login/okta/gh/{okta_org_name}")
    assert res.status_code == 302
    parsed_url = urlparse(res.url)
    assert parsed_url.hostname == "foo-bar.okta.com"
    assert parsed_url.path == "/oauth2/v1/authorize"

    parsed_query = parsed_url.query.split("&")
    raw_redirect_url = next(x for x in parsed_query if x.startswith("redirect_uri="))
    assert raw_redirect_url
    assert (
        unquote(raw_redirect_url.split("=")[1])
        == "http://localhost:8000/login/okta/callback"
    )


@pytest.mark.django_db
def test_okta_callback_login_success(
    signed_in_client: TestClient,
    okta_account: Account,
    okta_org: Owner,
    mocked_validate_id_token: Any,
    mocked_okta_token_request: Any,
):
    state = "test-state"
    session = signed_in_client.session
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None

    session["okta_cloud_oauth_state"] = state
    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }

    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"http://localhost:3000/github/{okta_org.username}"

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) == [okta_account.id]

    mocked_validate_id_token.assert_called_with("https://foo-bar.okta.com", ANY, ANY)


@pytest.mark.django_db
def test_okta_callback_login_success_multiple_accounts(
    signed_in_client: TestClient,
    okta_account: Account,
    okta_org: Owner,
    mocked_validate_id_token: Any,
    mocked_okta_token_request: Any,
):
    state = "test-state"
    session = signed_in_client.session
    # Put in a random account that's not current okta_account
    session[OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY] = [okta_account.id + 1]

    session["okta_cloud_oauth_state"] = state
    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }

    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )

    assert res.status_code == 302
    assert res.url == f"http://localhost:3000/github/{okta_org.username}"

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) == [
        okta_account.id + 1,
        okta_account.id,
    ]

    mocked_validate_id_token.assert_called_with("https://foo-bar.okta.com", ANY, ANY)


@pytest.mark.django_db
def test_okta_callback_missing_session(
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
):
    session = signed_in_client.session
    state = "test-state"
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state
    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )
    assert res.status_code == 403

    assert log_message_exists(
        "Trying to sign into Okta with no existing sign-in session.", caplog.records
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_missing_user(
    client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
):
    session = client.session
    state = "test-state"
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state
    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }
    session.save()

    res = client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )
    assert res.status_code == 403

    assert log_message_exists("User not logged in for Okta callback.", caplog.records)

    updated_session = client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_missing_okta_settings(
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
):
    session = signed_in_client.session
    state = "test-state"
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state
    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": 12345,
    }
    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )
    assert res.status_code == 404

    assert log_message_exists(
        "Okta settings not found. Cannot sign into Okta", caplog.records
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_no_code(
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
):
    session = signed_in_client.session
    state = "test-state"
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state
    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }
    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "state": state,
        },
    )
    assert res.status_code == 400

    assert log_message_exists(
        "No code is passed. Invalid callback. Cannot sign into Okta", caplog.records
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_perform_login_invalid_state(
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
):
    session = signed_in_client.session
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = "random-state"

    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }
    session.save()

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": "different-state",
        },
    )
    assert res.status_code == 302
    assert (
        res.url
        == f"http://localhost:3000/github/{okta_org.username}?error=invalid_state"
    )

    assert log_message_exists("Invalid state during Okta login", caplog.records)

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_perform_login_no_user_data(
    mocker: MockerFixture,
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
    mocked_okta_token_request: Any,
):
    state = "test-state"
    session = signed_in_client.session
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state

    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }
    session.save()

    mocked_okta_token_request.return_value = mocker.MagicMock(
        status_code=400,
    )

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )
    assert res.status_code == 302
    assert (
        res.url
        == f"http://localhost:3000/github/{okta_org.username}?error=invalid_token_response"
    )

    assert log_message_exists(
        "Can't log in. Invalid Okta Token Response", caplog.records
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_perform_login_invalid_id_token(
    mocker: MockerFixture,
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
    mocked_okta_token_request: Any,
):
    state = "test-state"
    session = signed_in_client.session
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state

    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }

    session.save()

    mocked_okta_token_request.return_value = mocker.MagicMock(
        status_code=200,
        json=lambda: {"access_token": "mock_access_token", "id_token": "mock_id_token"},
    )

    mocker.patch(
        "codecov_auth.views.okta_cloud.validate_id_token",
        side_effect=Exception("Invalid ID token"),
    )

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "code": "random-code",
            "state": state,
        },
    )
    assert res.status_code == 302
    assert (
        res.url
        == f"http://localhost:3000/github/{okta_org.username}?error=invalid_id_token"
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None


@pytest.mark.django_db
def test_okta_callback_perform_login_access_denied(
    mocker: MockerFixture,
    signed_in_client: TestClient,
    caplog: LogCaptureFixture,
    okta_org: Owner,
    okta_account: Account,
    mocked_okta_token_request: Any,
):
    state = "test-state"
    session = signed_in_client.session
    assert session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
    session["okta_cloud_oauth_state"] = state

    session[OKTA_CURRENT_SESSION] = {
        "org_ownerid": okta_org.ownerid,
        "okta_settings_id": okta_account.okta_settings.first().id,
    }
    session.save()

    mocked_okta_token_request.return_value = mocker.MagicMock(
        status_code=403,
    )

    res = signed_in_client.get(
        "/login/okta/callback",
        data={
            "state": state,
            "error": "access_denied",
        },
    )
    assert res.status_code == 302
    assert (
        res.url
        == f"http://localhost:3000/github/{okta_org.username}?error=access_denied"
    )

    updated_session = signed_in_client.session
    assert updated_session.get(OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY) is None
