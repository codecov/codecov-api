import enum
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Union

import sentry_sdk
from django.utils.functional import cached_property
from shared.api_archive.archive import ArchiveService
from shared.bundle_analysis import AssetReport as SharedAssetReport
from shared.bundle_analysis import (
    BundleAnalysisComparison as SharedBundleAnalysisComparison,
)
from shared.bundle_analysis import BundleAnalysisReport as SharedBundleAnalysisReport
from shared.bundle_analysis import BundleAnalysisReportLoader
from shared.bundle_analysis import BundleChange as SharedBundleChange
from shared.bundle_analysis import BundleReport as SharedBundleReport
from shared.bundle_analysis import ModuleReport as SharedModuleReport
from shared.bundle_analysis.models import AssetType
from shared.django_apps.bundle_analysis.service.bundle_analysis import (
    BundleAnalysisCacheConfigService,
)
from shared.storage import get_appropriate_storage_service

from codecov.db import sync_to_async
from core.models import Commit, Repository
from graphql_api.actions.measurements import (
    measurements_by_ids,
    measurements_last_uploaded_before_start_date,
)
from reports.models import CommitReport
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval, MeasurementName


@sentry_sdk.trace
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


def get_extension(filename: str) -> str:
    """
    Gets the file extension of the file without the dot
    """
    # At times file can be something like './index.js + 12 modules', only keep the real filepath
    filename = filename.split(" ")[0]
    # Retrieve the file extension with the dot
    _, file_extension = os.path.splitext(filename)
    # Return empty string if file has no extension
    if not file_extension or file_extension[0] != ".":
        return file_extension
    # Remove the dot in the extension
    file_extension = file_extension[1:]
    # At times file can be something like './index.js?module', remove the ?
    if "?" in file_extension:
        file_extension = file_extension[: file_extension.rfind("?")]

    return file_extension


class BundleAnalysisMeasurementsAssetType(enum.Enum):
    REPORT_SIZE = MeasurementName.BUNDLE_ANALYSIS_REPORT_SIZE
    JAVASCRIPT_SIZE = MeasurementName.BUNDLE_ANALYSIS_JAVASCRIPT_SIZE
    STYLESHEET_SIZE = MeasurementName.BUNDLE_ANALYSIS_STYLESHEET_SIZE
    FONT_SIZE = MeasurementName.BUNDLE_ANALYSIS_FONT_SIZE
    IMAGE_SIZE = MeasurementName.BUNDLE_ANALYSIS_IMAGE_SIZE
    ASSET_SIZE = MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE


class BundleAnalysisMeasurementData(object):
    def __init__(
        self,
        raw_measurements: List[dict],
        asset_type: Union[BundleAnalysisMeasurementsAssetType, str],
        asset_name: Optional[str],
        interval: Interval,
        after: Optional[datetime],
        before: datetime,
    ):
        self.raw_measurements = raw_measurements
        self.measurement_type = asset_type
        self.measurement_name = asset_name
        self.interval = interval
        self.after = after
        self.before = before

    @cached_property
    def asset_type(self) -> str:
        if isinstance(self.measurement_type, str):
            return self.measurement_type
        return self.measurement_type.name

    @cached_property
    def name(self) -> Optional[str]:
        return self.measurement_name

    @cached_property
    def size(self) -> Optional["BundleData"]:
        if len(self.raw_measurements) > 0:
            return BundleData(self.raw_measurements[-1]["avg"])

    @cached_property
    def change(self) -> Optional["BundleData"]:
        if len(self.raw_measurements) > 1:
            return BundleData(
                self.raw_measurements[-1]["avg"] - self.raw_measurements[0]["avg"]
            )

    @cached_property
    def measurements(self) -> Iterable[Dict[str, Any]]:
        if not self.raw_measurements:
            return []
        return fill_sparse_measurements(
            self.raw_measurements, self.interval, self.after, self.before
        )


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
    def __init__(self, size_in_bytes: int, gzip_size_in_bytes: Optional[int] = None):
        self.size_in_bytes = size_in_bytes
        self.size_in_bits = size_in_bytes * 8
        self.gzip_size_in_bytes = gzip_size_in_bytes

    @cached_property
    def size(self) -> BundleSize:
        gzip_size = (
            self.gzip_size_in_bytes
            if self.gzip_size_in_bytes is not None
            else int(float(self.size_in_bytes) * BundleSize.GZIP)
        )
        return BundleSize(
            gzip=gzip_size,
            uncompress=int(float(self.size_in_bytes) * BundleSize.UNCOMPRESS),
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
    def id(self) -> int:
        return self.asset.id

    @cached_property
    def name(self) -> str:
        return self.asset.hashed_name

    @cached_property
    def normalized_name(self) -> str:
        return self.asset.name

    @cached_property
    def extension(self) -> str:
        return get_extension(self.name)

    @cached_property
    def size_total(self) -> int:
        return self.asset.size

    @cached_property
    def gzip_size_total(self) -> int:
        return self.asset.gzip_size

    @cached_property
    def modules(self) -> List[ModuleReport]:
        return [ModuleReport(module) for module in self.asset.modules()]

    @cached_property
    def module_extensions(self) -> List[str]:
        return list({module.extension for module in self.modules})

    @cached_property
    def routes(self) -> Optional[List[str]]:
        return self.asset.routes()


@dataclass
class BundleReport(object):
    def __init__(self, report: SharedBundleReport, filters: Dict[str, Any] = {}):
        self.report = report
        self.filters = filters

    @cached_property
    def name(self) -> str:
        return self.report.name

    @cached_property
    def all_assets(self) -> List[AssetReport]:
        return [AssetReport(asset) for asset in self.report.asset_reports()]

    def assets(
        self, ordering: Optional[str] = None, ordering_desc: Optional[bool] = None
    ) -> List[AssetReport]:
        ordering_dict: Dict[str, Any] = {}
        if ordering:
            ordering_dict["ordering_column"] = ordering
        if ordering_desc is not None:
            ordering_dict["ordering_desc"] = ordering_desc
        return [
            AssetReport(asset)
            for asset in self.report.asset_reports(**{**ordering_dict, **self.filters})
        ]

    def asset(self, name: str) -> Optional[AssetReport]:
        for asset_report in self.all_assets:
            if asset_report.name == name:
                return asset_report

    @cached_property
    def size_total(self) -> int:
        return self.report.total_size(**self.filters)

    @cached_property
    def gzip_size_total(self) -> int:
        return self.report.total_gzip_size(**self.filters)

    @cached_property
    def module_extensions(self) -> List[str]:
        extensions = set()
        for asset in self.assets():
            extensions.update(asset.module_extensions)
        return list(extensions)

    @cached_property
    def module_count(self) -> int:
        return sum([len(asset.modules) for asset in self.assets()])

    @cached_property
    def is_cached(self) -> bool:
        return self.report.is_cached()

    @cached_property
    def info(self) -> dict:
        return self.report.info()

    @sync_to_async
    def cache_config(self, repo_id: int) -> bool:
        return BundleAnalysisCacheConfigService.get_cache_option(
            repo_id=repo_id, name=self.report.name
        )


@dataclass
class BundleReportInfo(object):
    def __init__(self, info: dict) -> None:
        self.info = info

    @cached_property
    def version(self) -> str:
        return self.info.get("version", "unknown")

    @cached_property
    def plugin_name(self) -> str:
        return self.info.get("plugin_name", "unknown")

    @cached_property
    def plugin_version(self) -> str:
        return self.info.get("plugin_version", "unknown")

    @cached_property
    def built_at(self) -> str:
        return str(datetime.fromtimestamp(self.info.get("built_at", 0) / 1000))

    @cached_property
    def duration(self) -> int:
        return self.info.get("duration", -1)

    @cached_property
    def bundler_name(self) -> str:
        return self.info.get("bundler_name", "unknown")

    @cached_property
    def bundler_version(self) -> str:
        return self.info.get("bundler_version", "unknown")


@dataclass
class BundleAnalysisReport(object):
    def __init__(self, report: SharedBundleAnalysisReport):
        self.report = report

    def bundle(
        self, name: str, filters: Dict[str, List[str]]
    ) -> Optional[BundleReport]:
        bundle_report = self.report.bundle_report(name)
        if bundle_report:
            return BundleReport(bundle_report, filters)

    @cached_property
    def bundles(self) -> List[BundleReport]:
        return [BundleReport(bundle) for bundle in self.report.bundle_reports()]

    @cached_property
    def size_total(self) -> int:
        return sum([bundle.size_total for bundle in self.bundles])

    @cached_property
    def is_cached(self) -> bool:
        return self.report.is_cached()


@dataclass
class BundleAnalysisComparison(object):
    def __init__(
        self,
        loader: BundleAnalysisReportLoader,
        base_report_key: str,
        head_report_key: str,
        repository: Repository,
    ):
        self.comparison = SharedBundleAnalysisComparison(
            loader,
            base_report_key,
            head_report_key,
            repository,
        )
        self.head_report = self.comparison.head_report

    @cached_property
    def bundles(self) -> List["BundleComparison"]:
        bundle_comparisons = []
        for bundle_change in self.comparison.bundle_changes():
            head_bundle_report = self.comparison.head_report.bundle_report(
                bundle_change.bundle_name
            )
            head_size = head_bundle_report.total_size() if head_bundle_report else 0
            bundle_comparisons.append(BundleComparison(bundle_change, head_size))
        return bundle_comparisons

    @cached_property
    def size_delta(self) -> int:
        return sum([change.size_delta for change in self.comparison.bundle_changes()])

    @cached_property
    def size_total(self) -> int:
        return BundleAnalysisReport(self.head_report).size_total


@dataclass
class BundleComparison(object):
    def __init__(self, bundle_change: SharedBundleChange, head_bundle_report_size: int):
        self.bundle_change = bundle_change
        self.head_bundle_report_size = head_bundle_report_size

    @cached_property
    def bundle_name(self) -> str:
        return self.bundle_change.bundle_name

    @cached_property
    def change_type(self) -> str:
        return self.bundle_change.change_type.value

    @cached_property
    def size_delta(self) -> int:
        return self.bundle_change.size_delta

    @cached_property
    def size_total(self) -> int:
        return self.head_bundle_report_size


class BundleAnalysisMeasurementsService(object):
    def __init__(
        self,
        repository: Repository,
        interval: Interval,
        before: datetime,
        after: Optional[datetime] = None,
        branch: Optional[str] = None,
    ) -> None:
        self.repository = repository
        self.interval = interval
        self.after = after
        self.before = before
        self.branch = branch

    @sentry_sdk.trace
    def _compute_measurements(
        self, measurable_name: str, measurable_ids: List[str]
    ) -> Dict[int, List[Dict[str, Any]]]:
        all_measurements = measurements_by_ids(
            repository=self.repository,
            measurable_name=measurable_name,
            measurable_ids=measurable_ids,
            interval=self.interval,
            after=self.after,
            before=self.before,
            branch=self.branch,
        )

        # Carry over previous available value for start date if its value is null
        for measurable_id, measurements in all_measurements.items():
            if self.after is not None and measurements[0]["timestamp_bin"] > self.after:
                carryover_measurement = measurements_last_uploaded_before_start_date(
                    owner_id=self.repository.author.ownerid,
                    repo_id=self.repository.repoid,
                    measurable_name=measurable_name,
                    measurable_id=measurable_id,
                    start_date=self.after,
                    branch=self.branch,
                )

                # Create a new datapoint in the measurements and prepend it to the existing list
                # If there isn't any measurements before the start date range, measurements will be untouched
                if carryover_measurement:
                    value = Decimal(carryover_measurement[0]["value"])
                    carryover = dict(measurements[0])
                    carryover["timestamp_bin"] = self.after
                    carryover["min"] = value
                    carryover["max"] = value
                    carryover["avg"] = value
                    all_measurements[measurable_id] = [carryover] + all_measurements[
                        measurable_id
                    ]

        return all_measurements

    @sentry_sdk.trace
    def compute_asset(
        self, asset_report: AssetReport
    ) -> Optional[BundleAnalysisMeasurementData]:
        asset = asset_report.asset
        if asset.asset_type != AssetType.JAVASCRIPT:
            return None

        measurements = self._compute_measurements(
            measurable_name=MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE.value,
            measurable_ids=[asset.uuid],
        )

        return BundleAnalysisMeasurementData(
            raw_measurements=list(measurements.get(asset.uuid, [])),
            asset_type=BundleAnalysisMeasurementsAssetType.JAVASCRIPT_SIZE,
            asset_name=asset.name,
            interval=self.interval,
            after=self.after,
            before=self.before,
        )

    @sentry_sdk.trace
    def compute_report(
        self,
        bundle_report: BundleReport,
        asset_type: BundleAnalysisMeasurementsAssetType,
    ) -> List[BundleAnalysisMeasurementData]:
        asset_uuid_to_name_mapping = {}
        if asset_type.value == MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE:
            measurable_ids = []
            for asset_report in bundle_report.all_assets:
                asset = asset_report.asset
                if asset.asset_type == AssetType.JAVASCRIPT:
                    measurable_ids.append(asset.uuid)
                    asset_uuid_to_name_mapping[asset.uuid] = asset.name
        else:
            measurable_ids = [bundle_report.name]

        measurements = self._compute_measurements(
            measurable_name=asset_type.value.value,
            measurable_ids=measurable_ids,
        )

        return [
            BundleAnalysisMeasurementData(
                raw_measurements=list(measurements.get(measurable_id, [])),
                asset_type=asset_type,
                asset_name=asset_uuid_to_name_mapping.get(measurable_id, None),
                interval=self.interval,
                after=self.after,
                before=self.before,
            )
            for measurable_id in measurable_ids
        ]
