from typing import List

from ariadne import ObjectType, UnionType

from graphql_api.types.comparison.comparison import MissingHeadReport
from services.bundle_analysis import BundleAnalysisReport, BundleData, BundleReport

bundle_analysis_report_result_bindable = UnionType("BundleAnalysisReportResult")
bundle_analysis_report_bindable = ObjectType("BundleAnalysisReport")


@bundle_analysis_report_result_bindable.type_resolver
def resolve_bundle_analysis_report_result_type(obj, *_):
    if isinstance(obj, BundleAnalysisReport):
        return "BundleAnalysisReport"
    elif isinstance(obj, MissingHeadReport):
        return "MissingHeadReport"


# TODO: depreacted with Issue 1199
@bundle_analysis_report_bindable.field("sizeTotal")
def resolve_size_total(bundles_analysis_report: BundleAnalysisReport, info) -> int:
    return bundles_analysis_report.size_total


# TODO: depreacted with Issue 1199
@bundle_analysis_report_bindable.field("loadTimeTotal")
def resolve_load_time_total(
    bundles_analysis_report: BundleAnalysisReport, info
) -> float:
    return bundles_analysis_report.load_time_total


@bundle_analysis_report_bindable.field("bundles")
def resolve_bundles(
    bundles_analysis_report: BundleAnalysisReport, info
) -> List[BundleReport]:
    return bundles_analysis_report.bundles


@bundle_analysis_report_bindable.field("bundle")
def resolve_bundle(
    bundles_analysis_report: BundleAnalysisReport, info, name: str
) -> BundleReport:
    return bundles_analysis_report.bundle(name)


@bundle_analysis_report_bindable.field("bundleData")
def resolve_bundle_data(
    bundles_analysis_report: BundleAnalysisReport, info
) -> BundleData:
    return BundleData(bundles_analysis_report.size_total)
