from typing import Any, List, Optional, Union

from ariadne import ObjectType, UnionType
from graphql import GraphQLResolveInfo

from graphql_api.types.comparison.comparison import MissingHeadReport
from graphql_api.types.enums import BundleLoadTypes
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
    asset_types = None
    if filters.get("report_groups"):
        asset_types = filters.get("report_groups")

    chunk_entry, chunk_initial = None, None
    if filters.get("load_types"):
        load_types = filters.get("load_types")

        # Compute chunk entry boolean
        if BundleLoadTypes.ENTRY in load_types and (
            BundleLoadTypes.INITIAL in load_types or BundleLoadTypes.LAZY in load_types
        ):
            chunk_entry = None
        elif BundleLoadTypes.ENTRY in load_types:
            chunk_entry = True
        elif (
            BundleLoadTypes.INITIAL in load_types or BundleLoadTypes.LAZY in load_types
        ):
            chunk_entry = False

        # Compute chunk initial boolean
        if BundleLoadTypes.INITIAL in load_types and BundleLoadTypes.LAZY in load_types:
            chunk_initial = None
        elif BundleLoadTypes.INITIAL in load_types:
            chunk_initial = True
        elif BundleLoadTypes.LAZY in load_types:
            chunk_initial = False

    return bundles_analysis_report.bundle(
        name,
        {
            "asset_types": asset_types,
            "chunk_entry": chunk_entry,
            "chunk_initial": chunk_initial,
        },
    )


@bundle_analysis_report_bindable.field("bundleData")
def resolve_bundle_data(
    bundles_analysis_report: BundleAnalysisReport, info: GraphQLResolveInfo
) -> BundleData:
    return BundleData(bundles_analysis_report.size_total)


@bundle_analysis_report_bindable.field("isCached")
def resolve_is_cached(bundle_report: BundleReport, info: GraphQLResolveInfo) -> bool:
    return bundle_report.is_cached
