import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core import models
from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.types.enums import UploadErrorEnum, UploadState
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
        upload = UploadFactory(report=commit_report, state=UploadState.ERROR.value)
        UploadErrorFactory(
            report_session=upload, error_code=UploadErrorEnum.FILE_NOT_IN_STORAGE.value
        )
        UploadErrorFactory(
            report_session=upload, error_code=UploadErrorEnum.REPORT_EXPIRED.value
        )
        UploadErrorFactory(
            report_session=upload, error_code=UploadErrorEnum.REPORT_EXPIRED.value
        )

        interactor_errors = async_to_sync(self.execute)(None, upload)

        assert len(interactor_errors.values()) == 3
        assert set(interactor_errors.values_list("error_code", flat=True)) == {
            UploadErrorEnum.FILE_NOT_IN_STORAGE.value,
            UploadErrorEnum.REPORT_EXPIRED.value,
            UploadErrorEnum.REPORT_EXPIRED.value,
        }

    def test_get_upload_errors_no_error(self):
        commit = CommitFactory(repository=self.repo,)
        commit_report = CommitReportFactory(commit=commit)

        # Some other fake errors on other uploads
        other_upload = UploadFactory(
            report=commit_report, state=UploadState.ERROR.value
        )
        other_upload_error_1 = UploadErrorFactory(report_session=other_upload)
        other_upload_error_2 = UploadErrorFactory(report_session=other_upload)

        another_upload = UploadFactory(
            report=commit_report, state=UploadState.ERROR.value
        )
        another_upload_error_1 = UploadErrorFactory(report_session=another_upload)
        another_upload_error_2 = UploadErrorFactory(report_session=another_upload)
        another_upload_error_3 = UploadErrorFactory(report_session=another_upload)

        upload = UploadFactory(report=commit_report)

        interactor_errors = async_to_sync(self.execute)(None, upload)

        assert len(interactor_errors.values()) == 0
