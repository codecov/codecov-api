from typing import List, Mapping

from ariadne import ObjectType

from services.bundle_analysis import (
    AssetReport,
    BundleData,
    BundleLoadTime,
    BundleReport,
    BundleSize,
    ModuleReport,
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


# ============= Bundle Module Bindable =============


@bundle_module_bindable.field("name")
def resolve_name(bundle_module: ModuleReport, info) -> str:
    return bundle_module.name


@bundle_module_bindable.field("bundleData")
def resolve_bundle_data(bundle_module: ModuleReport, info) -> int:
    return BundleData(bundle_module.size_total)


# ============= Bundle Asset Bindable =============


@bundle_asset_bindable.field("name")
def resolve_name(bundle_asset: AssetReport, info) -> str:
    return bundle_asset.name


@bundle_asset_bindable.field("normalizedName")
def resolve_normalized_name(bundle_asset: AssetReport, info) -> str:
    return bundle_asset.normalized_name


@bundle_asset_bindable.field("extension")
def resolve_extension(bundle_asset: AssetReport, info) -> str:
    return bundle_asset.extension


@bundle_asset_bindable.field("bundleData")
def resolve_bundle_data(bundle_asset: AssetReport, info) -> BundleData:
    return BundleData(bundle_asset.size_total)


@bundle_asset_bindable.field("modules")
def resolve_modules(bundle_asset: AssetReport, info) -> List[ModuleReport]:
    return bundle_asset.modules


@bundle_asset_bindable.field("moduleExtensions")
def resolve_module_extensions(bundle_asset: AssetReport, info) -> List[str]:
    return bundle_asset.module_extensions


# ============= Bundle Report Bindable =============


@bundle_report_bindable.field("name")
def resolve_name(bundle_report: BundleReport, info) -> str:
    return bundle_report.name


@bundle_report_bindable.field("moduleExtensions")
def resolve_module_extensions(bundle_report: BundleReport, info) -> List[str]:
    return bundle_report.module_extensions


@bundle_report_bindable.field("moduleCount")
def resolve_module_count(bundle_report: BundleReport, info) -> int:
    return bundle_report.module_count


@bundle_report_bindable.field("assets")
def resolve_assets(
    bundle_report: BundleReport,
    info,
    filters: Mapping = None,
) -> List[AssetReport]:
    extensions_filter = filters.get("moduleExtensions", None) if filters else None
    return list(bundle_report.assets(extensions_filter))


@bundle_report_bindable.field("asset")
def resolve_asset(bundle_report: BundleReport, info, name: str) -> AssetReport:
    return bundle_report.asset(name)


@bundle_report_bindable.field("bundleData")
def resolve_bundle_data(bundle_report: BundleReport, info) -> BundleData:
    return BundleData(bundle_report.size_total)
