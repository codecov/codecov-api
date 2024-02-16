from typing import List, Mapping

from ariadne import ObjectType

from services.bundle_analysis import (
    BundleData,
    BundleLoadTime,
    BundleReport,
    BundleSize,
)

bundle_data_bindable = ObjectType("BundleData")
bundle_module_bindable = ObjectType("BundleModule")
bundle_asset_bindable = ObjectType("BundleAsset")
bundle_report_bindable = ObjectType("BundleReport")

# ============= Bundle Data Bindable =============


@bundle_data_bindable.field("size")
def resolve_bundle_size(bundle_data: BundleData, info) -> BundleSize:
    return bundle_data.size


@bundle_data_bindable.field("loadTime")
def resolve_bundle_load_time(bundle_data: BundleData, info) -> BundleLoadTime:
    return bundle_data.load_time


# ============= Bundle Report Bindable =============


@bundle_report_bindable.field("name")
def resolve_name(bundle_report: BundleReport, info) -> str:
    return bundle_report.bundle_name


# TODO: depreacted with Issue 1199
@bundle_report_bindable.field("sizeTotal")
def resolve_size_total(bundle_report: BundleReport, info) -> int:
    return bundle_report.size_total


# TODO: depreacted with Issue 1199
@bundle_report_bindable.field("loadTimeTotal")
def resolve_load_time_total(bundle_report: BundleReport, info) -> float:
    return bundle_report.load_time_total


@bundle_report_bindable.field("moduleExtensions")
def resolve_module_extensions(bundle_report: BundleReport, info) -> List[str]:
    # TODO: Unimplemented
    return []


@bundle_report_bindable.field("moduleCount")
def resolve_module_count(bundle_report: BundleReport, info) -> List[str]:
    # TODO: Unimplemented
    return 0


@bundle_report_bindable.field("assets")
def resolve_assets(
    bundle_report: BundleReport,
    info,
    filters: Mapping = None,
) -> List[str]:
    # TODO: Unimplemented
    return []


@bundle_report_bindable.field("asset")
def resolve_asset(bundle_report: BundleReport, info, name: str) -> List[str]:
    # TODO: Unimplemented
    return None


@bundle_report_bindable.field("bundleData")
def resolve_bundle_data(bundle_report: BundleReport, info) -> BundleData:
    return BundleData(bundle_report.size_total)
