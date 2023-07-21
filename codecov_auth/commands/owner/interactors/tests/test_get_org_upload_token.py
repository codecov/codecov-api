from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OrganizationLevelTokenFactory, OwnerFactory

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
        assert token == None

    async def test_owner_with_org_upload_token(self):
        token = await GetOrgUploadToken(self.owner_with_upload_token, "github").execute(
            self.owner_with_upload_token
        )
        assert token
        assert len(str(token)) == 36  # default uuid
