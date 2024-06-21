from typing import Any, List, Optional, Union

from ariadne import ObjectType, UnionType
from graphql import GraphQLResolveInfo

from graphql_api.types.comparison.comparison import MissingHeadReport
from services.bundle_analysis import BundleAnalysisReport, BundleData, BundleReport

bundle_analysis_report_result_bindable = UnionType("BundleAnalysisReportResult")
bundle_analysis_report_bindable = ObjectType("BundleAnalysisReport")


@bundle_analysis_report_result_bindable.type_resolver
def resolve_bundle_analysis_report_result_type(
    obj: Union[BundleAnalysisReport, MissingHeadReport], *_: Any
) -> str:
    if isinstance(obj, BundleAnalysisReport):
        return "BundleAnalysisReport"
    elif isinstance(obj, MissingHeadReport):
        return "MissingHeadReport"


@bundle_analysis_report_bindable.field("bundles")
def resolve_bundles(
    bundles_analysis_report: BundleAnalysisReport, info: GraphQLResolveInfo
) -> List[BundleReport]:
    return bundles_analysis_report.bundles


@bundle_analysis_report_bindable.field("bundle")
def resolve_bundle(
    bundles_analysis_report: BundleAnalysisReport,
    info: GraphQLResolveInfo,
    name: str,
    filters: dict[str, list[str]] = {},
) -> Optional[BundleReport]:
    return bundles_analysis_report.bundle(name, filters)


@bundle_analysis_report_bindable.field("bundleData")
def resolve_bundle_data(
    bundles_analysis_report: BundleAnalysisReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(bundles_analysis_report.size_total)
