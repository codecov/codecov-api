from datetime import datetime
from typing import List, Mapping, Optional

from ariadne import ObjectType, convert_kwargs_to_snake_case
from graphql import GraphQLResolveInfo

from codecov.db import sync_to_async
from graphql_api.types.enums import OrderingDirection
from services.bundle_analysis import (
    AssetReport,
    BundleAnalysisMeasurementData,
    BundleAnalysisMeasurementsAssetType,
    BundleAnalysisMeasurementsService,
    BundleData,
    BundleLoadTime,
    BundleReport,
    BundleSize,
    ModuleReport,
)
from timeseries.models import Interval

bundle_data_bindable = ObjectType("BundleData")
bundle_module_bindable = ObjectType("BundleModule")
bundle_asset_bindable = ObjectType("BundleAsset")
bundle_report_bindable = ObjectType("BundleReport")


# ============= Bundle Data Bindable =============


@bundle_data_bindable.field("size")
def resolve_bundle_size(
    bundle_data: BundleData, info: GraphQLResolveInfo
) -> BundleSize:
    return bundle_data.size


@bundle_data_bindable.field("loadTime")
def resolve_bundle_load_time(
    bundle_data: BundleData, info: GraphQLResolveInfo
) -> BundleLoadTime:
    return bundle_data.load_time


# ============= Bundle Module Bindable =============


@bundle_module_bindable.field("name")
def resolve_bundle_module_name(
    bundle_module: ModuleReport, info: GraphQLResolveInfo
) -> str:
    return bundle_module.name


@bundle_module_bindable.field("bundleData")
def resolve_bundle_module_bundle_data(
    bundle_module: ModuleReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(bundle_module.size_total)


# ============= Bundle Asset Bindable =============


@bundle_asset_bindable.field("name")
def resolve_bundle_asset_name(
    bundle_asset: AssetReport, info: GraphQLResolveInfo
) -> str:
    return bundle_asset.name


@bundle_asset_bindable.field("normalizedName")
def resolve_normalized_name(bundle_asset: AssetReport, info: GraphQLResolveInfo) -> str:
    return bundle_asset.normalized_name


@bundle_asset_bindable.field("extension")
def resolve_extension(bundle_asset: AssetReport, info: GraphQLResolveInfo) -> str:
    return bundle_asset.extension


@bundle_asset_bindable.field("bundleData")
def resolve_bundle_asset_bundle_data(
    bundle_asset: AssetReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(bundle_asset.size_total)


@bundle_asset_bindable.field("modules")
def resolve_modules(
    bundle_asset: AssetReport, info: GraphQLResolveInfo
) -> List[ModuleReport]:
    return bundle_asset.modules


@bundle_asset_bindable.field("measurements")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_asset_report_measurements(
    bundle_asset: AssetReport,
    info: GraphQLResolveInfo,
    interval: Interval,
    before: datetime,
    after: Optional[datetime] = None,
    branch: Optional[str] = None,
) -> Optional[BundleAnalysisMeasurementData]:
    bundle_analysis_measurements = BundleAnalysisMeasurementsService(
        repository=info.context["commit"].repository,
        interval=interval,
        before=before,
        after=after,
        branch=branch,
    )
    return bundle_analysis_measurements.compute_asset(bundle_asset)


# ============= Bundle Report Bindable =============


@bundle_report_bindable.field("name")
def resolve_name(bundle_report: BundleReport, info: GraphQLResolveInfo) -> str:
    return bundle_report.name


@bundle_report_bindable.field("moduleCount")
def resolve_module_count(bundle_report: BundleReport, info: GraphQLResolveInfo) -> int:
    return bundle_report.module_count


@bundle_report_bindable.field("assets")
def resolve_assets(
    bundle_report: BundleReport,
    info: GraphQLResolveInfo,
) -> List[AssetReport]:
    return list(bundle_report.assets())


@bundle_report_bindable.field("asset")
def resolve_asset(
    bundle_report: BundleReport, info: GraphQLResolveInfo, name: str
) -> Optional[AssetReport]:
    return bundle_report.asset(name)


@bundle_report_bindable.field("bundleData")
def resolve_bundle_data(
    bundle_report: BundleReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(bundle_report.size_total)


@bundle_report_bindable.field("measurements")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_bundle_report_measurements(
    bundle_report: BundleReport,
    info: GraphQLResolveInfo,
    interval: Interval,
    before: datetime,
    after: Optional[datetime] = None,
    branch: Optional[str] = None,
    filters: Mapping = {},
    ordering_direction: Optional[OrderingDirection] = OrderingDirection.ASC,
) -> List[BundleAnalysisMeasurementData]:
    if not filters.get("asset_types", []):
        measurable_names = [item for item in list(BundleAnalysisMeasurementsAssetType)]
    else:
        measurable_names = [
            BundleAnalysisMeasurementsAssetType[item] for item in filters["asset_types"]
        ]

    bundle_analysis_measurements = BundleAnalysisMeasurementsService(
        repository=info.context["commit"].repository,
        interval=interval,
        before=before,
        after=after,
        branch=branch,
    )

    measurements = []
    for name in measurable_names:
        measurements.extend(
            bundle_analysis_measurements.compute_report(bundle_report, asset_type=name)
        )

    return sorted(
        measurements,
        key=lambda c: c.asset_type,
        reverse=ordering_direction == OrderingDirection.DESC,
    )
