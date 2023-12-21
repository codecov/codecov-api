from typing import Optional

from shared.bundle_analysis import BundleAnalysisReport, BundleAnalysisReportLoader
from shared.storage import get_appropriate_storage_service

from core.models import Commit
from reports.models import CommitReport
from services.archive import ArchiveService


def load_report(
    commit: Commit, report_code: Optional[str] = None
) -> Optional[BundleAnalysisReport]:
    storage = get_appropriate_storage_service()

    commit_report = commit.reports.filter(
        report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        code=report_code,
    ).first()
    if commit_report is None:
        return None

    loader = BundleAnalysisReportLoader(
        storage_service=storage,
        repo_key=ArchiveService.get_archive_hash(commit.repository),
    )
    return loader.load(commit_report.external_id)
