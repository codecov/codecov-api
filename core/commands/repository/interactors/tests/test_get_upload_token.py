from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from ..get_upload_token import GetUploadTokenInteractor


class GetUploadTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo_in_org = RepositoryFactory(author=self.org)
        self.random_repo = RepositoryFactory()
        self.owner = OwnerFactory(organizations=[self.org.ownerid])

    # helper to execute the interactor
    def execute(self, *args):
        return GetUploadTokenInteractor(self.owner, self.owner.service).execute(*args)

    async def test_fetch_upload_token_random_repo(self):
        token = await self.execute(self.random_repo)
        assert token is None

    async def test_fetch_upload_token_repo_in_my_org(self):
        token = await self.execute(self.repo_in_org)
        assert token is self.repo_in_org.upload_token
