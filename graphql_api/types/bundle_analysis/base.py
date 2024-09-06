from datetime import datetime
from typing import Dict, List, Mapping, Optional, Union

from ariadne import ObjectType, convert_kwargs_to_snake_case
from graphql import GraphQLResolveInfo

from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from graphql_api.types.enums import AssetOrdering, OrderingDirection
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


def _find_index_by_cursor(assets: List, cursor: str) -> int:
    try:
        for i, asset in enumerate(assets):
            if asset.id == int(cursor):
                return i
    except ValueError:
        pass
    return -1


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
    return BundleData(bundle_asset.size_total, bundle_asset.gzip_size_total)


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


@bundle_report_bindable.field("assetsPaginated")
def resolve_assets_paginated(
    bundle_report: BundleReport,
    info: GraphQLResolveInfo,
    ordering: AssetOrdering = AssetOrdering.SIZE,
    ordering_direction: OrderingDirection = OrderingDirection.DESC,
    first: Optional[int] = None,
    after: Optional[str] = None,
    last: Optional[int] = None,
    before: Optional[str] = None,
) -> Union[Dict[str, object], ValidationError]:
    if first is not None and last is not None:
        return ValidationError("First and last can not be used at the same time")
    if after is not None and before is not None:
        return ValidationError("After and before can not be used at the same time")

    # All filtered assets before pagination
    assets = list(
        bundle_report.assets(
            ordering=ordering.value,
            ordering_desc=ordering_direction.value == OrderingDirection.DESC.value,
        )
    )

    total_count, has_next_page, has_previous_page = len(assets), False, False
    start_cursor, end_cursor = None, None

    # Apply cursors to edges
    if after is not None:
        after_edge = _find_index_by_cursor(assets, after)
        if after_edge > -1:
            assets = assets[after_edge + 1 :]

    if before is not None:
        before_edge = _find_index_by_cursor(assets, before)
        if before_edge > -1:
            assets = assets[:before_edge]

    # Slice edges by return size
    if first is not None and first >= 0:
        if len(assets) > first:
            assets = assets[:first]
            has_next_page = True

    if last is not None and last >= 0:
        if len(assets) > last:
            assets = assets[len(assets) - last :]
            has_previous_page = True

    if assets:
        start_cursor, end_cursor = assets[0].id, assets[-1].id

    return {
        "edges": [{"cursor": asset.id, "node": asset} for asset in assets],
        "total_count": total_count,
        "page_info": {
            "has_next_page": has_next_page,
            "has_previous_page": has_previous_page,
            "start_cursor": start_cursor,
            "end_cursor": end_cursor,
        },
    }


@bundle_report_bindable.field("asset")
def resolve_asset(
    bundle_report: BundleReport, info: GraphQLResolveInfo, name: str
) -> Optional[AssetReport]:
    return bundle_report.asset(name)


@bundle_report_bindable.field("bundleData")
def resolve_bundle_data(
    bundle_report: BundleReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(
        bundle_report.size_total,
        bundle_report.gzip_size_total,
    )


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


@bundle_report_bindable.field("isCached")
def resolve_bundle_report_is_cached(
    bundle_report: BundleReport, info: GraphQLResolveInfo
) -> bool:
    return bundle_report.is_cached
