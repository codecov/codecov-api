from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Union

import sentry_sdk
from ariadne import ObjectType
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
    BundleReportInfo,
    BundleSize,
    ModuleReport,
)
from timeseries.models import Interval

ASSET_TYPE_UNKNOWN = "UNKNOWN_SIZE"

bundle_data_bindable = ObjectType("BundleData")
bundle_module_bindable = ObjectType("BundleModule")
bundle_asset_bindable = ObjectType("BundleAsset")
bundle_report_bindable = ObjectType("BundleReport")
bundle_report_info_bindable = ObjectType("BundleReportInfo")


def _find_index_by_cursor(assets: List, cursor: str) -> int:
    try:
        for i, asset in enumerate(assets):
            if asset.id == int(cursor):
                return i
    except ValueError:
        pass
    return -1


def _compute_unknown_asset_size_raw_measurements(fetched_data: dict) -> List[dict]:
    """
    Computes measurements for the unknown asset types, some asset types are not in
    the predetermined list of types so we must compute those measurements manually.
    The heuristic will be to get the measurements of the bundle type (ie total bundle size)
    then substract it from all the known asset type measurements, leaving with only the unknown.
    """
    unknown_raw_measurements = deepcopy(
        fetched_data[BundleAnalysisMeasurementsAssetType.REPORT_SIZE][
            0
        ].raw_measurements
    )

    for name, measurements in fetched_data.items():
        if name not in (
            BundleAnalysisMeasurementsAssetType.REPORT_SIZE,
            BundleAnalysisMeasurementsAssetType.ASSET_SIZE,
        ):
            raw_measurements = measurements[0].raw_measurements
            for i in range(len(raw_measurements)):
                if len(unknown_raw_measurements) != len(raw_measurements):
                    return []
                unknown_raw_measurements[i]["min"] -= raw_measurements[i]["min"]
                unknown_raw_measurements[i]["max"] -= raw_measurements[i]["max"]
                unknown_raw_measurements[i]["avg"] -= raw_measurements[i]["avg"]

    return unknown_raw_measurements


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


@sentry_sdk.trace
@bundle_asset_bindable.field("measurements")
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


@bundle_asset_bindable.field("routes")
def resolve_routes(
    bundle_asset: AssetReport, info: GraphQLResolveInfo
) -> Optional[List[str]]:
    return bundle_asset.routes


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


@sentry_sdk.trace
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


@bundle_report_bindable.field("bundleDataFiltered")
def resolve_bundle_report_filtered(
    bundle_report: BundleReport,
    info: GraphQLResolveInfo,
    filters: dict[str, list[str]] = {},
) -> BundleData:
    group = filters.get("report_group")
    return BundleData(
        bundle_report.report.total_size(asset_types=[group] if group else None),
        bundle_report.report.total_gzip_size(asset_types=[group] if group else None),
    )


@sentry_sdk.trace
@bundle_report_bindable.field("measurements")
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
    asset_types = list(filters.get("asset_types", []))
    bundle_analysis_measurements = BundleAnalysisMeasurementsService(
        repository=info.context["commit"].repository,
        interval=interval,
        before=before,
        after=after,
        branch=branch,
    )

    # All measureable names we need to fetch to compute the requested asset types
    if not asset_types:
        measurables_to_fetch = list(BundleAnalysisMeasurementsAssetType)
    elif ASSET_TYPE_UNKNOWN in asset_types:
        measurables_to_fetch = [
            BundleAnalysisMeasurementsAssetType.REPORT_SIZE,
            BundleAnalysisMeasurementsAssetType.JAVASCRIPT_SIZE,
            BundleAnalysisMeasurementsAssetType.STYLESHEET_SIZE,
            BundleAnalysisMeasurementsAssetType.FONT_SIZE,
            BundleAnalysisMeasurementsAssetType.IMAGE_SIZE,
        ]
    else:
        measurables_to_fetch = [
            BundleAnalysisMeasurementsAssetType[item] for item in asset_types
        ]

    # Retrieve all the measurements necessary to compute the requested asset types
    fetched_data = {}
    for name in measurables_to_fetch:
        fetched_data[name] = bundle_analysis_measurements.compute_report(
            bundle_report, asset_type=name
        )

    # All measureable name we need to return
    if not asset_types:
        measurables_to_display = list(BundleAnalysisMeasurementsAssetType)
    else:
        measurables_to_display = [
            BundleAnalysisMeasurementsAssetType[item]
            for item in asset_types
            if item != ASSET_TYPE_UNKNOWN
        ]

    measurements = []
    for measurable in measurables_to_display:
        measurements.extend(fetched_data[measurable])

    # Compute for unknown asset type size if necessary
    if not asset_types or ASSET_TYPE_UNKNOWN in asset_types:
        unknown_size_raw_measurements = _compute_unknown_asset_size_raw_measurements(
            fetched_data
        )
        measurements.append(
            BundleAnalysisMeasurementData(
                raw_measurements=unknown_size_raw_measurements,
                asset_type=ASSET_TYPE_UNKNOWN,
                asset_name=None,
                interval=interval,
                after=after,
                before=before,
            )
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


@bundle_report_bindable.field("cacheConfig")
def resolve_bundle_report_cache_config(
    bundle_report: BundleReport, info: GraphQLResolveInfo
) -> bool:
    return bundle_report.cache_config(info.context["commit"].repository.pk)


@bundle_report_bindable.field("info")
def resolve_bundle_report_info(
    bundle_report: BundleReport, info: GraphQLResolveInfo
) -> BundleReportInfo:
    return BundleReportInfo(bundle_report.info)


@bundle_report_info_bindable.field("version")
def resolve_bundle_report_info_version(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.version


@bundle_report_info_bindable.field("pluginName")
def resolve_bundle_report_info_plugin_name(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.plugin_name


@bundle_report_info_bindable.field("pluginVersion")
def resolve_bundle_report_info_plugin_version(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.plugin_version


@bundle_report_info_bindable.field("builtAt")
def resolve_bundle_report_info_built_at(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.built_at


@bundle_report_info_bindable.field("duration")
def resolve_bundle_report_info_duration(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> int:
    return bundle_report_info.duration


@bundle_report_info_bindable.field("bundlerName")
def resolve_bundle_report_info_bundler_name(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.bundler_name


@bundle_report_info_bindable.field("bundlerVersion")
def resolve_bundle_report_info_bundler_version(
    bundle_report_info: BundleReportInfo, info: GraphQLResolveInfo
) -> str:
    return bundle_report_info.bundler_version
