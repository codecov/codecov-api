from unittest.mock import patch

import pytest
from shared.bundle_analysis import BundleAnalysisReport, StoragePaths
from shared.bundle_analysis.storage import BUCKET_NAME
from shared.storage.memory import MemoryStorageService

from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory
from services.archive import ArchiveService
from services.bundle_analysis import load_report


@pytest.mark.django_db
@patch("services.bundle_analysis.get_appropriate_storage_service")
def test_load_report(get_storage_service):
    storage = MemoryStorageService({})
    get_storage_service.return_value = storage

    repo = RepositoryFactory()
    commit = CommitFactory(repository=repo)

    # no commit report record
    assert load_report(commit) is None

    commit_report = CommitReportFactory(
        commit=commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
    )

    storage_path = StoragePaths.bundle_report.path(
        repo_key=ArchiveService.get_archive_hash(repo),
        report_key=commit_report.external_id,
    )

    # nothing in storage
    assert load_report(commit) is None

    with open("./services/tests/samples/bundle_report.sqlite", "rb") as f:
        storage.write_file(BUCKET_NAME, storage_path, f)

    report = load_report(commit)
    assert report is not None
    assert isinstance(report, BundleAnalysisReport)
