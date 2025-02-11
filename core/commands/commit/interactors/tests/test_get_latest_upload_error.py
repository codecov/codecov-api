from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from core.commands.commit.interactors.get_latest_upload_error import (
    GetLatestUploadErrorInteractor,
)
from graphql_api.types.enums import UploadErrorEnum
from reports.models import CommitReport
from reports.tests.factories import (
    CommitReportFactory,
    UploadErrorFactory,
    UploadFactory,
)


class GetLatestUploadErrorInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.commit = self._create_commit_with_errors()
        self.commit_with_no_errors = CommitFactory(repository=self.repo)
        self.single_error_commit = self._create_commit_with_single_error()

    def _create_commit_with_errors(self):
        commit = CommitFactory(repository=self.repo)
        report = CommitReportFactory(
            commit=commit, report_type=CommitReport.ReportType.TEST_RESULTS
        )
        upload = UploadFactory(report=report)

        # Create two errors with different timestamps
        UploadErrorFactory(
            report_session=upload,
            created_at="2024-01-01T10:00:00Z",
            error_code=UploadErrorEnum.FILE_NOT_IN_STORAGE,
            error_params={"error_message": "First error"},
        )
        UploadErrorFactory(
            report_session=upload,
            created_at="2024-01-01T11:00:00Z",
            error_code=UploadErrorEnum.REPORT_EMPTY,
            error_params={"error_message": "Latest error"},
        )
        return commit

    def _create_commit_with_single_error(self):
        commit = CommitFactory(repository=self.repo)
        report = CommitReportFactory(
            commit=commit,
            report_type=CommitReport.ReportType.TEST_RESULTS,
        )
        upload = UploadFactory(report=report)
        UploadErrorFactory(
            report_session=upload,
            error_code=UploadErrorEnum.UNKNOWN_PROCESSING,
            error_params={"error_message": "Some other error"},
        )
        return commit

    def execute(self, commit, owner=None):
        service = owner.service if owner else "github"
        return GetLatestUploadErrorInteractor(owner, service).execute(commit)

    async def test_when_no_errors_then_returns_none(self):
        result = await self.execute(commit=self.commit_with_no_errors, owner=self.org)
        assert result is None

    async def test_when_multiple_errors_then_returns_most_recent(self):
        result = await self.execute(commit=self.commit, owner=self.org)
        assert result == {
            "error_code": UploadErrorEnum.REPORT_EMPTY,
            "error_message": "Latest error",
        }

    async def test_when_single_error_then_returns_error(self):
        result = await self.execute(commit=self.single_error_commit, owner=self.org)
        assert result == {
            "error_code": UploadErrorEnum.UNKNOWN_PROCESSING,
            "error_message": "Some other error",
        }

    async def test_return_none_on_raised_error(self):
        with patch(
            "core.commands.commit.interactors.get_latest_upload_error.GetLatestUploadErrorInteractor._get_latest_error",
            side_effect=Exception("Test error"),
        ):
            result = await self.execute(commit=self.commit, owner=self.org)
            assert result is None
