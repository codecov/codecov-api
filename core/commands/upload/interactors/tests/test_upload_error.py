import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core import models
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import (
    CommitReportFactory,
    UploadErrorFactory,
    UploadFactory,
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
        commit = CommitFactory(repository=self.repo,)
        commit_report = CommitReportFactory(commit=commit)
        upload = UploadFactory(report=commit_report, state="error")
        UploadErrorFactory(report_session=upload, error_code="orange")
        UploadErrorFactory(report_session=upload, error_code="apple")
        UploadErrorFactory(report_session=upload, error_code="kiwi")

        interactor_errors = async_to_sync(self.execute)(None, upload)

        assert len(interactor_errors.values()) == 3
        assert set(interactor_errors.values_list("error_code", flat=True)) == {
            "orange",
            "apple",
            "kiwi",
        }

    def test_get_upload_errors_no_error(self):
        commit = CommitFactory(repository=self.repo,)
        commit_report = CommitReportFactory(commit=commit)

        # Some other fake errors on other uploads
        other_upload = UploadFactory(report=commit_report, state="error")
        UploadErrorFactory(report_session=other_upload)
        UploadErrorFactory(report_session=other_upload)

        another_upload = UploadFactory(report=commit_report, state="error")
        UploadErrorFactory(report_session=another_upload)
        UploadErrorFactory(report_session=another_upload)
        UploadErrorFactory(report_session=another_upload)

        upload = UploadFactory(report=commit_report)

        interactor_errors = async_to_sync(self.execute)(None, upload)

        assert len(interactor_errors.values()) == 0
