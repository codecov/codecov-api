import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.tests.factories import OwnerFactory

from ..set_upload_token_required import SetUploadTokenRequiredInteractor


class SetUploadTokenRequiredInteractorTest(TransactionTestCase):
    def setUp(self):
        self.current_user = OwnerFactory(username="codecov-user")
        self.service = "github"
        self.owner = OwnerFactory(
            username="codecov-owner",
            service=self.service,
        )

        self.owner_with_admins = OwnerFactory(
            username="codecov-admin-owner",
            service=self.service,
            admins=[self.current_user.ownerid],
        )

        self.interactor = SetUploadTokenRequiredInteractor(
            current_owner=self.owner,
            service=self.service,
            current_user=self.current_user,
        )

    @async_to_sync
    async def execute(
        self,
        interactor: SetUploadTokenRequiredInteractor | None = None,
        input: dict | None = None,
    ):
        if not interactor:
            interactor = self.interactor
        return await interactor.execute(input)

    @pytest.mark.asyncio
    async def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            await self.execute(
                interactor=SetUploadTokenRequiredInteractor(
                    current_owner=None,
                    service=self.service,
                    current_user=AnonymousUser(),
                ),
                input={
                    "tokens_required": True,
                    "org_username": self.owner.username,
                },
            )

    @pytest.mark.asyncio
    async def test_validation_error_when_owner_not_found(self):
        with pytest.raises(ValidationError):
            await self.execute(
                input={
                    "tokens_required": True,
                    "org_username": "non-existent-user",
                },
            )

    @pytest.mark.asyncio
    async def test_unauthorized_error_when_user_is_not_admin(self):
        with pytest.raises(Unauthorized):
            await self.execute(
                input={
                    "tokens_required": True,
                    "org_username": self.owner.username,
                },
            )

    @pytest.mark.asyncio
    async def test_set_tokens_required_when_user_is_admin(self):
        input_data = {
            "tokens_required": True,
            "org_username": self.owner_with_admins.username,
        }

        interactor = SetUploadTokenRequiredInteractor(
            current_owner=self.current_user, service=self.service
        )
        result = await self.execute(interactor=interactor, input=input_data)

        assert result == True
        self.owner_with_admins.refresh_from_db()
        assert self.owner_with_admins.tokens_required == True

    @pytest.mark.asyncio
    async def test_set_tokens_required_to_false(self):
        self.owner_with_admins.tokens_required = True
        self.owner_with_admins.save()

        input_data = {
            "tokens_required": False,
            "org_username": self.owner_with_admins.username,
        }

        interactor = SetUploadTokenRequiredInteractor(
            current_owner=self.current_user, service=self.service
        )
        result = await self.execute(interactor=interactor, input=input_data)

        assert result == False
        self.owner_with_admins.refresh_from_db()
        assert self.owner_with_admins.tokens_required == False
