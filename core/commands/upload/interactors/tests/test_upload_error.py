import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
from reports.tests.factories import (
    CommitReportFactory,
    UploadFactory,
    UploadErrorFactory,
)

from ..get_upload_error import GetUploadErrorInteractor


class GetUploadErrorInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo, state="error")
        self.commit_report = CommitReportFactory(commit=self.commit)

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetUploadErrorInteractor(current_user, service).execute(*args)

    def test_get_upload_errors(self):
        upload = UploadFactory(report=self.commit_report)
        test_errors = [
            UploadErrorFactory(report_session=upload),
            UploadErrorFactory(report_session=upload, error_code="test"),
            UploadErrorFactory(report_session=upload, error_code="banana"),
        ]
        interactor_errors = async_to_sync(self.execute)(None, self.commit)

        for test_error in test_errors:
            [current_error] = interactor_errors.filter(
                error_code=test_error.error_code
            ).values()

            assert current_error["error_code"] == test_error.error_code.test

    # def test_get_upload_errors_no_error(self):
    #     # Errors not related to the requested upload
    #     UploadFactory()
    #     UploadFactory()
    #     UploadFactory()
    #     errors = async_to_sync(self.execute)(None, self.commit)
    #     assert errors is None
