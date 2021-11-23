import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import UploadFactory

from ..get_uploads_of_commit import GetUploadsOfCommitInteractor


class GetUploadsOfCommitInteractorTest(TransactionTestCase):
    def setUp(self):
        self.commit_with_no_upload = CommitFactory()
        self.upload_one = UploadFactory()
        self.upload_two = UploadFactory(report=self.upload_one.report)
        self.commit_with_upload = self.upload_two.report.commit

        # making sure everything is public
        self.commit_with_no_upload.repository.private = False
        self.commit_with_no_upload.repository.save()
        self.commit_with_upload.repository.private = False
        self.commit_with_upload.repository.save()

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetUploadsOfCommitInteractor(current_user, service).execute(*args)

    async def test_fetch_when_no_reports(self):
        uploads = await self.execute(None, self.commit_with_no_upload)
        assert len(uploads) is 0

    def test_fetch_when_reports(self):
        # self.execute returns a lazy queryset so we need to wrap it with
        # async_to_sync
        uploads = async_to_sync(self.execute)(None, self.commit_with_upload)
        assert len(uploads) is 2
