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

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetUploadErrorInteractor(current_user, service).execute(*args)

    def test_get_upload_errors(self):
        commit = CommitFactory(repository=self.repo, state="error")
        commit_report = CommitReportFactory(commit=commit)
        upload = UploadFactory(report=commit_report)

        test_errors = [
            UploadErrorFactory(report_session=upload),
            UploadErrorFactory(report_session=upload),
            UploadErrorFactory(report_session=upload),
        ]

        interactor_errors = async_to_sync(self.execute)(None, commit)

        for test_error in test_errors:
            [current_error] = interactor_errors.filter(
                error_code=test_error.error_code
            ).values()

            assert current_error["error_code"] == test_error.error_code

    def test_get_upload_errors_no_error(self):
        my_commit = CommitFactory(repository=self.repo, state="complete")
        other_commit = CommitFactory(repository=self.repo, state="error")
        my_report = CommitReportFactory(commit=my_commit)
        other_report = CommitReportFactory(commit=other_commit)
        my_upload = UploadFactory(report=my_report)
        other_upload = UploadFactory(report=other_report)

        test_errors = [
            UploadErrorFactory(report_session=other_upload),
            UploadErrorFactory(report_session=other_upload),
            UploadErrorFactory(report_session=other_upload),
        ]

        interactor_errors = async_to_sync(self.execute)(None, my_commit)

        for test_error in test_errors:
            for error in interactor_errors.values():
                assert error["error_code"] != test_error.error_code
