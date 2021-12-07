from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory

from ..get_uploads_number_per_user import GetUploadsNumberPerUserInteractor


class GetUploadsNumberPerUserInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user_with_no_uplaods = OwnerFactory()
        self.user_with_uplaods = OwnerFactory()
        repo = RepositoryFactory.create(author=self.user_with_uplaods)
        commit = CommitFactory.create(repository=repo)
        report = CommitReportFactory.create(commit=commit)
        for i in range(150):
            UploadFactory.create(report=report)

    async def test_with_no_uploads(self):
        owner = self.user_with_no_uplaods
        uploads = await GetUploadsNumberPerUserInteractor(self, owner).execute(owner)
        assert uploads == 0

    async def test_with_number_of_uploads(self):
        owner = self.user_with_uplaods
        uploads = await GetUploadsNumberPerUserInteractor(self, owner).execute(owner)
        assert uploads == 150
