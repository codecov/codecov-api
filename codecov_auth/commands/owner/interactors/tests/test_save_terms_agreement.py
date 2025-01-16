from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from freezegun.api import FakeDatetime
from shared.django_apps.codecov_auth.tests.factories import UserFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError

from ..save_terms_agreement import SaveTermsAgreementInteractor


class UpdateSaveTermsAgreementInteractorTest(TransactionTestCase):
    def setUp(self):
        self.current_user = UserFactory(name="codecov-user")
        self.updated_at = FakeDatetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @async_to_sync
    def execute(self, current_user, input=None):
        real_input = {
            "business_email": None,
            "terms_agreement": False,
            "marketing_consent": False,
        }
        if input:
            real_input.update(input)
        return SaveTermsAgreementInteractor(None, "github", current_user).execute(
            input=real_input,
        )

    #### Start of older tests

    @freeze_time("2022-01-01T00:00:00")
    def test_deprecated_update_user_when_agreement_is_false(self):
        self.execute(
            current_user=self.current_user,
            input={"terms_agreement": False, "customer_intent": "Business"},
        )
        before_refresh_business_email = self.current_user.email

        assert self.current_user.terms_agreement == False
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == before_refresh_business_email

    @freeze_time("2022-01-01T00:00:00")
    def test_deprecated_update_user_when_agreement_is_true(self):
        self.execute(
            current_user=self.current_user,
            input={"terms_agreement": True, "customer_intent": "Business"},
        )
        before_refresh_business_email = self.current_user.email

        assert self.current_user.terms_agreement == True
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == before_refresh_business_email

    @freeze_time("2022-01-01T00:00:00")
    def test_deprecated_update_owner_and_user_when_email_is_not_empty(self):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "terms_agreement": True,
                "customer_intent": "Business",
            },
        )

        assert self.current_user.terms_agreement == True
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == "something@email.com"

    def test_deprecated_validation_error_when_customer_intent_invalid(self):
        with pytest.raises(ValidationError):
            self.execute(
                current_user=self.current_user,
                input={"terms_agreement": None, "customer_intent": "invalid"},
            )

    def test_deprecated_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(
                current_user=AnonymousUser(),
                input={
                    "business_email": "something@email.com",
                    "terms_agreement": True,
                    "customer_intent": "Business",
                },
            )

    def test_deprecated_email_opt_in_saved_in_db(self):
        self.execute(
            current_user=self.current_user,
            input={
                "terms_agreement": True,
                "marketing_consent": True,
                "customer_intent": "Business",
            },
        )
        self.current_user.refresh_from_db()
        assert self.current_user.email_opt_in == True

    @patch(
        "codecov_auth.commands.owner.interactors.save_terms_agreement.SaveTermsAgreementInteractor.send_data_to_marketo"
    )
    def test_deprecated_marketo_called_only_with_consent(
        self, mock_send_data_to_marketo
    ):
        self.execute(
            current_user=self.current_user,
            input={
                "terms_agreement": True,
                "marketing_consent": True,
                "customer_intent": "Business",
            },
        )

        mock_send_data_to_marketo.assert_called_once()

    @patch(
        "codecov_auth.commands.owner.interactors.save_terms_agreement.SaveTermsAgreementInteractor.send_data_to_marketo"
    )
    def test_deprecated_marketo_not_called_without_consent(
        self, mock_send_data_to_marketo
    ):
        self.execute(
            current_user=self.current_user,
            input={
                "terms_agreement": True,
                "marketing_consent": False,
                "customer_intent": "Business",
            },
        )

        mock_send_data_to_marketo.assert_not_called()

    #### End of older tests

    @freeze_time("2022-01-01T00:00:00")
    def test_update_user_when_agreement_is_false(self):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": False,
            },
        )
        before_refresh_business_email = self.current_user.email

        assert self.current_user.terms_agreement == False
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == before_refresh_business_email

    @freeze_time("2022-01-01T00:00:00")
    def test_update_user_when_agreement_is_true(self):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": True,
            },
        )
        before_refresh_business_email = self.current_user.email

        assert self.current_user.terms_agreement == True
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == before_refresh_business_email

    @freeze_time("2022-01-01T00:00:00")
    def test_update_owner_and_user_when_email_and_name_are_not_empty(self):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": True,
            },
        )

        assert self.current_user.terms_agreement == True
        assert self.current_user.terms_agreement_at == self.updated_at

        self.current_user.refresh_from_db()
        assert self.current_user.email == "something@email.com"
        assert self.current_user.name == "codecov-user"

    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(
                current_user=AnonymousUser(),
                input={
                    "business_email": "something@email.com",
                    "name": "codecov-user",
                    "terms_agreement": True,
                },
            )

    def test_email_opt_in_saved_in_db(self):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": True,
                "marketing_consent": True,
            },
        )
        self.current_user.refresh_from_db()
        assert self.current_user.email_opt_in == True

    @patch(
        "codecov_auth.commands.owner.interactors.save_terms_agreement.SaveTermsAgreementInteractor.send_data_to_marketo"
    )
    def test_marketo_called_only_with_consent(self, mock_send_data_to_marketo):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": True,
                "marketing_consent": True,
            },
        )

        mock_send_data_to_marketo.assert_called_once()

    @patch(
        "codecov_auth.commands.owner.interactors.save_terms_agreement.SaveTermsAgreementInteractor.send_data_to_marketo"
    )
    def test_marketo_not_called_without_consent(self, mock_send_data_to_marketo):
        self.execute(
            current_user=self.current_user,
            input={
                "business_email": "something@email.com",
                "name": "codecov-user",
                "terms_agreement": True,
                "marketing_consent": False,
            },
        )

        mock_send_data_to_marketo.assert_not_called()
