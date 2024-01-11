from dataclasses import dataclass
from typing import Optional

from django.utils.functional import cached_property
from shared.bundle_analysis import (
    BundleAnalysisComparison as SharedBundleAnalysisComparison,
)
from shared.bundle_analysis import BundleAnalysisReport, BundleAnalysisReportLoader
from shared.bundle_analysis import BundleChange as SharedBundleChange
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


def load_time_conversion(size):
    """
    Converts total size in bytes to approximate time (in seconds) to download using a 3G internet (3 Mbps)
    """
    return round((8 * size) / (1024 * 1024 * 3), 1)


@dataclass
class BundleAnalysisComparison(object):
    def __init__(
        self,
        loader: BundleAnalysisReportLoader,
        base_report_key: str,
        head_report_key: str,
    ):
        self.comparison = SharedBundleAnalysisComparison(
            loader,
            base_report_key,
            head_report_key,
        )
        self.bundle_comparisons = []
        self.total_size_delta = 0
        self.total_size = sum(
            [
                report.total_size()
                for report in self.comparison.head_report.bundle_reports()
            ]
        )

        for bundle_change in self.comparison.bundle_changes():
            self.total_size_delta += bundle_change.size_delta
            head_bundle_report = self.comparison.head_report.bundle_report(
                bundle_change.bundle_name
            )
            if self.comparison.head_report and head_bundle_report:
                head_bundle_report_size = head_bundle_report.total_size()
            else:
                head_bundle_report_size = 0
            self.bundle_comparisons.append(
                BundleComparison(bundle_change, head_bundle_report_size)
            )

        self.cleanup()

    def cleanup(self) -> None:
        if self.comparison.head_report:
            self.comparison.head_report.cleanup()
        if self.comparison.base_report:
            self.comparison.base_report.cleanup()

    @cached_property
    def bundles(self):
        return self.bundle_comparisons

    @cached_property
    def size_delta(self):
        return self.total_size_delta

    @cached_property
    def size_total(self):
        return self.total_size

    @cached_property
    def load_time_delta(self):
        return load_time_conversion(self.total_size_delta)

    @cached_property
    def load_time_total(self):
        return load_time_conversion(self.total_size)


@dataclass
class BundleComparison(object):
    def __init__(self, bundle_change: SharedBundleChange, head_bundle_report_size: int):
        self.bundle_change = bundle_change
        self.head_bundle_report_size = head_bundle_report_size

    @cached_property
    def bundle_name(self):
        return self.bundle_change.bundle_name

    @cached_property
    def change_type(self):
        return self.bundle_change.change_type.value

    @cached_property
    def size_delta(self):
        return self.bundle_change.size_delta

    @cached_property
    def size_total(self):
        return self.head_bundle_report_size

    @cached_property
    def load_time_delta(self):
        return load_time_conversion(self.bundle_change.size_delta)

    @cached_property
    def load_time_total(self):
        return load_time_conversion(self.head_bundle_report_size)
