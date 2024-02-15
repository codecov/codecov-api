from ariadne import ObjectType

from services.bundle_analysis import BundleReport

bundle_size_bindable = ObjectType("BundleSize")
bundle_load_time_bindable = ObjectType("BundleLoadTime")
bundle_data_bindable = ObjectType("BundleData")
bundle_module_bindable = ObjectType("BundleModule")
bundle_asset_bindable = ObjectType("BundleAsset")
bundle_report_bindable = ObjectType("BundleReport")


@bundle_report_bindable.field("name")
def resolve_name(bundle_report: BundleReport, info) -> str:
    return bundle_report.bundle_name


@bundle_report_bindable.field("sizeTotal")
def resolve_size_total(bundle_report: BundleReport, info) -> int:
    return bundle_report.size_total


@bundle_report_bindable.field("loadTimeTotal")
def resolve_load_time_total(bundle_report: BundleReport, info) -> float:
    return bundle_report.load_time_total
