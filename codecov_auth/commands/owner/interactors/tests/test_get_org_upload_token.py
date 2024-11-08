import pytest
from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
    OwnerFactory,
)

from codecov.commands.exceptions import Unauthenticated, Unauthorized

from ..get_org_upload_token import GetOrgUploadToken


class GetOrgUploadTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner_with_no_upload_token = OwnerFactory()
        self.owner_with_upload_token = OwnerFactory(plan="users-enterprisem")
        OrganizationLevelTokenFactory(owner=self.owner_with_upload_token)

    async def test_owner_with_no_org_upload_token(self):
        token = await GetOrgUploadToken(
            self.owner_with_no_upload_token, "github"
        ).execute(self.owner_with_no_upload_token)
        assert token is None

    async def test_owner_with_org_upload_token(self):
        token = await GetOrgUploadToken(self.owner_with_upload_token, "github").execute(
            self.owner_with_upload_token
        )
        assert token
        assert len(str(token)) == 36  # default uuid

    async def test_owner_with_org_upload_token_and_anonymous_user(self):
        with pytest.raises(Unauthenticated):
            token = await GetOrgUploadToken(None, "github").execute(
                self.owner_with_upload_token
            )

            assert token is None

    async def test_owner_with_org_upload_token_and_unauthorized_user(self):
        with pytest.raises(Unauthorized):
            token = await GetOrgUploadToken(
                self.owner_with_upload_token, "github"
            ).execute(self.owner_with_no_upload_token)

            assert token is None
