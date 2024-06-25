import json
from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase, TransactionTestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory
from services.sentry import (
    SentryInvalidStateError,
    SentryState,
    SentryUserAlreadyExistsError,
    decode_state,
    is_sentry_user,
    save_sentry_state,
    send_user_webhook,
)


@override_settings(SENTRY_JWT_SHARED_SECRET="secret")
class DecodeStateTests(TestCase):
    def setUp(self):
        self.decoded_state = {"user_id": "sentry-user-id", "org_id": "sentry-org-id"}
        self.state = jwt.encode(self.decoded_state, "secret", algorithm="HS256")

    def test_decode_state(self):
        res = decode_state(self.state)
        assert res.data == self.decoded_state

    @override_settings(SENTRY_JWT_SHARED_SECRET="wrong")
    def test_decode_state_wrong_secret(self):
        res = decode_state(self.state)
        assert res is None

    def test_decode_state_malformed(self):
        res = decode_state("malformed")
        assert res is None


class SaveSentryStateTests(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory()

        self.decode_state_patcher = patch("services.sentry.decode_state")
        self.decode_state = self.decode_state_patcher.start()
        self.decode_state.return_value = SentryState(
            {
                "user_id": "sentry-user-id",
                "org_id": "sentry-org-id",
            }
        )
        self.addCleanup(self.decode_state_patcher.stop)

    def test_save_sentry_state(self):
        state_mock = MagicMock()
        save_sentry_state(self.owner, state_mock)

        self.decode_state.assert_called_once_with(state_mock)

        self.owner.refresh_from_db()
        assert self.owner.sentry_user_id == "sentry-user-id"
        assert self.owner.sentry_user_data == {
            "user_id": "sentry-user-id",
            "org_id": "sentry-org-id",
        }

    def test_save_sentry_state_invalid_state(self):
        self.decode_state.return_value = None

        with self.assertRaises(SentryInvalidStateError):
            save_sentry_state(self.owner, MagicMock())

        self.owner.refresh_from_db()
        assert self.owner.sentry_user_id is None
        assert self.owner.sentry_user_data is None

    def test_save_sentry_state_duplicate_user_id(self):
        OwnerFactory(sentry_user_id="sentry-user-id")
        with self.assertRaises(SentryUserAlreadyExistsError):
            save_sentry_state(self.owner, MagicMock())

        self.owner.refresh_from_db()
        assert self.owner.sentry_user_id is None
        assert self.owner.sentry_user_data is None


class IsSentryUserTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory()

    def test_owner_has_sentry_user_id(self):
        self.owner.sentry_user_id = "testing"
        assert is_sentry_user(self.owner) == True

    def test_owner_missing_sentry_user_id(self):
        self.owner.sentry_user_id = None
        assert is_sentry_user(self.owner) == False


@patch("services.task.TaskService.http_request")
class SendWebhookTests(TestCase):
    def setUp(self):
        self.user = OwnerFactory(
            sentry_user_id="sentry-user-id",
            sentry_user_data={"user_id": "sentry-user-id", "org_id": "sentry-org-id"},
        )
        self.org = OwnerFactory(
            service="github",
            service_id="org-service-id",
        )

    @override_settings(
        SENTRY_USER_WEBHOOK_URL="https://example.com", SENTRY_JWT_SHARED_SECRET="secret"
    )
    def test_webhook(self, http_request):
        send_user_webhook(self.user, self.org)

        encoded_state = jwt.encode(
            {
                "user_id": self.user.sentry_user_id,
                "org_id": self.user.sentry_user_data.get("org_id"),
                "codecov_owner_id": self.user.pk,
                "codecov_organization_id": self.org.pk,
                "service": self.org.service,
                "service_id": self.org.service_id,
            },
            "secret",
            algorithm="HS256",
        )

        http_request.assert_called_once_with(
            url="https://example.com",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Codecov",
            },
            data=json.dumps({"state": f"{encoded_state}"}),
        )

    @override_settings(SENTRY_USER_WEBHOOK_URL=None)
    def test_webhook_no_url(self, http_request):
        send_user_webhook(self.user, self.org)
        assert not http_request.called
