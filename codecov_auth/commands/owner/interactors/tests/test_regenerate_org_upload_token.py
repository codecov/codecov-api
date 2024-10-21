import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError

from ..regenerate_org_upload_token import RegenerateOrgUploadTokenInteractor


class RegenerateOrgUploadTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.random_user = OwnerFactory()
        self.owner = OwnerFactory(username="codecovv", plan="users-enterprisem")
        self.user_not_part_of_org = OwnerFactory(
            username="random", plan="users-enterprisem"
        )

    def execute(self, owner, org_owner=None):
        return RegenerateOrgUploadTokenInteractor(owner, "github").execute(
            owner=org_owner
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(owner="")

    async def test_when_validation_no_owner_found(self):
        with pytest.raises(ValidationError):
            await self.execute(owner=self.random_user)

    async def test_regenerate_org_upload_token_user_not_part_of_org(self):
        with pytest.raises(Unauthorized):
            await self.execute(
                owner=self.user_not_part_of_org, org_owner=self.owner.username
            )

    async def test_regenerate_org_upload_token(self):
        token = await self.execute(owner=self.owner, org_owner=self.owner.username)
        assert token is not None
