import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError

from ..set_upload_token_required import SetUploadTokenRequiredInteractor


class SetUploadTokenRequiredInteractorTest(TransactionTestCase):
    def setUp(self):
        self.service = "github"
        self.current_user = OwnerFactory(username="codecov-user")
        self.owner = OwnerFactory(
            username="codecov-owner",
            service=self.service,
        )
        self.owner_with_admins = OwnerFactory(
            username="codecov-admin-owner",
            service=self.service,
            admins=[self.current_user.ownerid],
        )

    @async_to_sync
    async def execute(
        self, current_user, org_username=None, upload_token_required=True
    ):
        interactor = SetUploadTokenRequiredInteractor(current_user, self.service)
        return await interactor.execute(
            {
                "upload_token_required": upload_token_required,
                "org_username": org_username,
            }
        )

    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(
                current_user=None,
                org_username=self.owner.username,
            )

    def test_validation_error_when_owner_not_found(self):
        with pytest.raises(ValidationError):
            self.execute(
                current_user=self.current_user,
                org_username="non-existent-user",
            )

    def test_unauthorized_error_when_user_is_not_admin(self):
        with pytest.raises(Unauthorized):
            self.execute(
                current_user=self.current_user,
                org_username=self.owner.username,
            )

    def test_set_upload_token_required_when_user_is_admin(self):
        self.current_user.organizations = [self.owner_with_admins.ownerid]
        self.current_user.save()

        self.execute(
            current_user=self.current_user,
            org_username=self.owner_with_admins.username,
        )

        self.owner_with_admins.refresh_from_db()
        assert self.owner_with_admins.upload_token_required_for_public_repos == True

    def test_set_upload_token_required_to_false(self):
        self.current_user.organizations = [self.owner_with_admins.ownerid]
        self.current_user.save()

        self.execute(
            current_user=self.current_user,
            org_username=self.owner_with_admins.username,
            upload_token_required=False,
        )

        self.owner_with_admins.refresh_from_db()
        assert self.owner_with_admins.upload_token_required_for_public_repos == False

    def test_set_upload_token_required_to_null_raises_validation_error(self):
        self.current_user.organizations = [self.owner_with_admins.ownerid]
        self.current_user.save()

        with pytest.raises(ValidationError):
            self.execute(
                current_user=self.current_user,
                org_username=self.owner_with_admins.username,
                upload_token_required=None,
            )
