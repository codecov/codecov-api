import os
from dataclasses import dataclass
from typing import List, Optional

from django.utils.functional import cached_property
from shared.bundle_analysis import AssetReport as SharedAssetReport
from shared.bundle_analysis import (
    BundleAnalysisComparison as SharedBundleAnalysisComparison,
)
from shared.bundle_analysis import BundleAnalysisReport as SharedBundleAnalysisReport
from shared.bundle_analysis import BundleAnalysisReportLoader
from shared.bundle_analysis import BundleChange as SharedBundleChange
from shared.bundle_analysis import BundleReport as SharedBundleReport
from shared.bundle_analysis import ModuleReport as SharedModuleReport
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


def get_extension(filename: str) -> str:
    """
    Gets the file extension of the file without the dot
    also handling cases where ?* exists after the . (eg production.js?exports)
    """
    _, file_extension = os.path.splitext(filename)
    if not file_extension or file_extension[0] != ".":
        return file_extension

    file_extension = file_extension[1:]

    if "?" in file_extension:
        return file_extension[: file_extension.rfind("?")]

    return file_extension


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
class ModuleReport(object):
    def __init__(self, module: SharedModuleReport):
        self.module = module

    @cached_property
    def name(self) -> str:
        return self.module.name

    @cached_property
    def size_total(self) -> int:
        return self.module.size

    @cached_property
    def extension(self) -> str:
        return get_extension(self.name)


@dataclass
class AssetReport(object):
    def __init__(self, asset: SharedAssetReport):
        self.asset = asset
        self.all_modules = None

    @cached_property
    def name(self) -> str:
        return self.asset.name

    @cached_property
    def normalized_name(self) -> str:
        return self.asset.hashed_name

    @cached_property
    def extension(self) -> str:
        return get_extension(self.name)

    @cached_property
    def size_total(self) -> int:
        return self.asset.size

    @cached_property
    def modules(self) -> ModuleReport:
        return [ModuleReport(module) for module in self.asset.modules()]

    @cached_property
    def module_extensions(self) -> List[str]:
        return list(set([module.extension for module in self.modules]))


@dataclass
class BundleReport(object):
    def __init__(self, report: SharedBundleReport):
        self.report = report

    @cached_property
    def name(self) -> str:
        return self.report.name

    @cached_property
    def all_assets(self) -> List[AssetReport]:
        return [AssetReport(asset) for asset in self.report.asset_reports()]

    def assets(self, extensions: Optional[List[str]]) -> List[AssetReport]:
        all_assets = self.all_assets

        # TODO: Unimplemented
        print("filtered by", extensions)
        filtered_assets = all_assets

        return filtered_assets

    def asset(self, name: str) -> AssetReport:
        for asset_report in self.all_assets:
            if asset_report.name == name:
                return asset_report

    @cached_property
    def size_total(self) -> int:
        return self.report.total_size()

    # To be deprecated after FE uses BundleData
    @cached_property
    def load_time_total(self) -> float:
        return load_time_conversion(self.report.total_size())


@dataclass
class BundleAnalysisReport(object):
    def __init__(self, report: SharedBundleAnalysisReport):
        self.report = report
        self.cleanup()

    def cleanup(self) -> None:
        if self.report and self.report.db_session:
            self.report.db_session.close()

    def bundle(self, name):
        return BundleReport(self.report.bundle_report(name))

    @cached_property
    def bundles(self):
        return [BundleReport(bundle) for bundle in self.report.bundle_reports()]

    @cached_property
    def size_total(self):
        return sum([bundle.size_total for bundle in self.bundles])

    @cached_property
    def load_time_total(self):
        return load_time_conversion(self.size_total)


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
