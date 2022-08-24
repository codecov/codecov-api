import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OrganizationLevelTokenFactory, OwnerFactory

from ..regenerate_org_upload_token import RegenerateOrgUploadTokenInteractor


class RegenerateOrgUploadTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(name="codecov", plan="users-enterprisem")
        self.owner_no_token = OwnerFactory(name="random", plan="users-enterprisem")
        self.owner_free_plan = OwnerFactory(name="rula", plan="users-free")
        self.owner_with_no_token = OwnerFactory(name="no_token")
        self.upload_token = OrganizationLevelTokenFactory(
            owner=self.owner, token="testnnwlwev51mxuzrjghmbsg3pm1t7nop4l"
        )
        self.random_user = OwnerFactory()

    def execute(self, user, owner=None):
        current_user = user or AnonymousUser()
        return RegenerateOrgUploadTokenInteractor(current_user, "github").execute(
            owner=owner
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="")

    async def test_when_validation_no_owner_found(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.random_user)

    async def test_when_validation_not_enterprise(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.random_user, owner=self.owner_free_plan.name)

    async def test_regenerate_org_upload_token_creates_new_token(self):
        token = await self.execute(
            user=self.owner_no_token, owner=self.owner_no_token.name
        )
        assert token is not None

    async def test_regenerate_org_upload_token(self):
        token = await self.execute(user=self.owner, owner=self.owner.name)
        assert token is not None
        assert token != self.upload_token.token
