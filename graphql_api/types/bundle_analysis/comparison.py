from ariadne import ObjectType, UnionType

from graphql_api.types.comparison.comparison import (
    FirstPullRequest,
    MissingBaseCommit,
    MissingBaseReport,
    MissingHeadCommit,
    MissingHeadReport,
)
from services.bundle_analysis import (
    BundleAnalysisComparison,
    BundleComparison,
    BundleData,
)

bundle_analysis_comparison_result_bindable = UnionType("BundleAnalysisComparisonResult")
bundle_analysis_comparison_bindable = ObjectType("BundleAnalysisComparison")
bundle_comparison_bindable = ObjectType("BundleComparison")


@bundle_analysis_comparison_result_bindable.type_resolver
def resolve_bundle_analysis_comparison_result_type(obj, *_):
    if isinstance(obj, BundleAnalysisComparison):
        return "BundleAnalysisComparison"
    elif isinstance(obj, MissingHeadCommit):
        return "MissingHeadCommit"
    elif isinstance(obj, MissingBaseCommit):
        return "MissingBaseCommit"
    elif isinstance(obj, FirstPullRequest):
        return "FirstPullRequest"
    elif isinstance(obj, MissingHeadReport):
        return "MissingHeadReport"
    elif isinstance(obj, MissingBaseReport):
        return "MissingBaseReport"


@bundle_analysis_comparison_bindable.field("bundles")
def resolve_ba_comparison_bundles(
    bundles_analysis_comparison: BundleAnalysisComparison, info
):
    return bundles_analysis_comparison.bundles


@bundle_analysis_comparison_bindable.field("bundleData")
def resolve_ba_comparison_bundle_data(
    bundles_analysis_comparison: BundleAnalysisComparison, info
) -> BundleData:
    return BundleData(bundles_analysis_comparison.size_total)


@bundle_analysis_comparison_bindable.field("bundleChange")
def resolve_ba_comparison_bundle_delta(
    bundles_analysis_comparison: BundleAnalysisComparison, info
) -> BundleData:
    return BundleData(bundles_analysis_comparison.size_delta)


@bundle_comparison_bindable.field("name")
def resolve_name(bundle_comparison: BundleComparison, info):
    return bundle_comparison.bundle_name


@bundle_comparison_bindable.field("changeType")
def resolve_change_type(bundle_comparison: BundleComparison, info):
    return bundle_comparison.change_type


@bundle_comparison_bindable.field("bundleData")
def resolve_bundle_data(bundle_comparison: BundleComparison, info) -> BundleData:
    return BundleData(bundle_comparison.size_total)


@bundle_comparison_bindable.field("bundleChange")
def resolve_bundle_delta(bundle_comparison: BundleComparison, info) -> BundleData:
    return BundleData(bundle_comparison.size_delta)
