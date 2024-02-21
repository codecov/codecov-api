from dataclasses import dataclass
from typing import Optional

from django.utils.functional import cached_property
from shared.bundle_analysis import (
    BundleAnalysisComparison as SharedBundleAnalysisComparison,
)
from shared.bundle_analysis import BundleAnalysisReport as SharedBundleAnalysisReport
from shared.bundle_analysis import BundleAnalysisReportLoader
from shared.bundle_analysis import BundleChange as SharedBundleChange
from shared.storage import get_appropriate_storage_service

from core.models import Commit
from reports.models import CommitReport
from services.archive import ArchiveService


def load_report(
    commit: Commit, report_code: Optional[str] = None
) -> Optional[SharedBundleAnalysisReport]:
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


# TODO: depreacted with Issue 1199
def load_time_conversion(size):
    """
    Converts total size in bytes to approximate time (in seconds) to download using a 3G internet (3 Mbps)
    """
    return round((8 * size) / (1024 * 1024 * 3), 1)


@dataclass
class BundleLoadTime:
    """
    Value in Milliseconds
    Reference for speed estimation:
    https://firefox-source-docs.mozilla.org/devtools-user/network_monitor/throttling/index.html
    """

    # Speed of internet in bits per second (as reference above)
    THREE_G_SPEED = 750 * 1000  # Equivalent to 750 Kbps
    HIGH_SPEED = 30 * 1000 * 1000  # Equivalent to 30 Mbps

    # Computed load time in milliseconds
    three_g: int
    high_speed: int


@dataclass
class BundleSize:
    """
    Value in Bytes
    """

    # Compression ratio compared to uncompressed size
    GZIP = 0.001
    UNCOMPRESS = 1.0

    # Computed size in bytes
    gzip: int
    uncompress: int


@dataclass
class BundleData:
    def __init__(self, size_in_bytes: int):
        self.size_in_bytes = size_in_bytes
        self.size_in_bits = size_in_bytes * 8

    @cached_property
    def size(self) -> BundleSize:
        return BundleSize(
            gzip=int(self.size_in_bytes * BundleSize.GZIP),
            uncompress=int(self.size_in_bytes * BundleSize.UNCOMPRESS),
        )

    @cached_property
    def load_time(self) -> BundleLoadTime:
        return BundleLoadTime(
            three_g=int((self.size_in_bits / BundleLoadTime.THREE_G_SPEED) * 1000),
            high_speed=int((self.size_in_bits / BundleLoadTime.HIGH_SPEED) * 1000),
        )


@dataclass
class BundleAnalysisReport(object):
    def __init__(self, report: SharedBundleAnalysisReport):
        self.report = report
        self.report_bundles = []
        self.total_size = 0
        for bundle in self.report.bundle_reports():
            total_size = bundle.total_size()
            self.report_bundles.append(BundleReport(bundle.name, total_size))
            self.total_size += total_size

        self.cleanup()

    def cleanup(self) -> None:
        if self.report:
            self.report.cleanup(delete_file=False)

    @cached_property
    def bundles(self):
        return self.report_bundles

    @cached_property
    def size_total(self):
        return self.total_size

    @cached_property
    def load_time_total(self):
        return load_time_conversion(self.total_size)


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


@dataclass
class BundleReport(object):
    def __init__(self, name, report_size: int):
        self.bundle_name = name
        self.size_total = report_size
        self.load_time_total = load_time_conversion(report_size)
