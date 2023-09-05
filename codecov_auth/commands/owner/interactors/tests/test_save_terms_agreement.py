import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov.commands.exceptions import ValidationError
from codecov_auth.models import User
from codecov_auth.tests.factories import OwnerFactory

from ..save_terms_agreement import SaveTermsAgreementInteractor


class UpdateSaveTermsAgreementInteractorTest(TransactionTestCase):
    def setUp(self):
        self.current_owner = OwnerFactory(
            username="random-user-123",
            service="github",
            business_email="asdfasdfa@gmail.com",
        )

    @async_to_sync
    def execute(
        self, current_owner, input={"businessEmail": None, "termsAgreement": False}
    ):
        return SaveTermsAgreementInteractor(current_owner, "github").execute(
            input=input,
        )

    @freeze_time("2022-01-01T00:00:00")
    def test_update_user_when_agreement_is_false(self):
        self.execute(current_owner=self.current_owner, input={"termsAgreement": False})
        before_refresh_business_email = self.current_owner.business_email

        user: User = User.objects.filter(id=self.current_owner.user_id).first()
        assert user.terms_agreement == False
        assert user.terms_agreement_at == timezone.datetime(2022, 1, 1)

        self.current_owner.refresh_from_db()
        self.current_owner.business_email == before_refresh_business_email

    @freeze_time("2022-01-02T00:00:00")
    def test_update_user_when_agreement_is_true(self):
        self.execute(current_owner=self.current_owner, input={"termsAgreement": True})
        before_refresh_business_email = self.current_owner.business_email

        user: User = User.objects.filter(id=self.current_owner.user_id).first()
        assert user.terms_agreement == True
        assert user.terms_agreement_at == timezone.datetime(2022, 1, 2)

        self.current_owner.refresh_from_db()
        self.current_owner.business_email == before_refresh_business_email

    @freeze_time("2022-01-03T00:00:00")
    def test_update_owner_and_user_when_email_is_not_empty(self):
        self.execute(
            current_owner=self.current_owner,
            input={"businessEmail": "something@email.com", "termsAgreement": True},
        )

        user: User = User.objects.filter(id=self.current_owner.user_id).first()
        assert user.terms_agreement == True
        assert user.terms_agreement_at == timezone.datetime(2022, 1, 3)

        self.current_owner.refresh_from_db()
        self.current_owner.business_email == "something@email.com"

    def test_validation_error_when_terms_is_none(self):
        with pytest.raises(ValidationError):
            self.execute(
                current_owner=self.current_owner, input={"termsAgreement": None}
            )

    def test_owner_has_no_user(self):
        owner_without_user = OwnerFactory(
            username="random-user-123",
            service="github",
            business_email="asdfasdfa@gmail.com",
            user=None,
        )
        with pytest.raises(ValidationError) as e:
            self.execute(
                current_owner=owner_without_user,
                input={"businessEmail": "something@email.com", "termsAgreement": True},
            )
        assert str(e.value) == "Owner does not have an associated user"
