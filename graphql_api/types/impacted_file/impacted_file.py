import hashlib
from typing import List, Union

from ariadne import ObjectType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async
from shared.reports.types import ReportTotals
from shared.torngit.exceptions import TorngitClientError

from graphql_api.types.errors import ProviderError, QueryError, UnknownPath
from graphql_api.types.segment_comparison.segment_comparison import SegmentComparisons
from services.comparison import Comparison, Segment
from services.profiling import ProfilingSummary

impacted_file_bindable = ObjectType("ImpactedFile")
from services.comparison import ImpactedFile


@impacted_file_bindable.field("fileName")
def resolve_file_name(impacted_file: ImpactedFile, info) -> str:
    return impacted_file.file_name


@impacted_file_bindable.field("headName")
def resolve_head_name(impacted_file: ImpactedFile, info) -> str:
    return impacted_file.head_name


@impacted_file_bindable.field("baseName")
def resolve_base_name(impacted_file: ImpactedFile, info) -> str:
    return impacted_file.base_name


@impacted_file_bindable.field("headCoverage")
def resolve_head_coverage(impacted_file: ImpactedFile, info) -> ReportTotals:
    return impacted_file.head_coverage


@impacted_file_bindable.field("baseCoverage")
def resolve_base_coverage(impacted_file: ImpactedFile, info) -> ReportTotals:
    return impacted_file.base_coverage


@impacted_file_bindable.field("patchCoverage")
def resolve_patch_coverage(impacted_file: ImpactedFile, info) -> ReportTotals:
    return impacted_file.patch_coverage


@impacted_file_bindable.field("changeCoverage")
def resolve_change_coverage(impacted_file: ImpactedFile, info) -> float:
    return impacted_file.change_coverage


@impacted_file_bindable.field("hashedPath")
def resolve_hashed_path(impacted_file: ImpactedFile, info) -> str:
    path = impacted_file.head_name
    encoded_path = path.encode()
    md5_path = hashlib.md5(encoded_path)

    return md5_path.hexdigest()


@impacted_file_bindable.field("segments")
@sync_to_async
@convert_kwargs_to_snake_case
def resolve_segments(
    impacted_file: ImpactedFile, info, filters=None
) -> Union[UnknownPath, ProviderError, SegmentComparisons]:
    if "comparison" not in info.context:
        return QueryError("cannot query segments in this context")

    if filters is None:
        filters = {}

    comparison: Comparison = info.context["comparison"]
    path = impacted_file.head_name

    try:
        file_comparison = comparison.get_file_comparison(
            path, with_src=True, bypass_max_diff=True
        )
    except TorngitClientError as e:
        if e.code == 404:
            return UnknownPath(f"path does not exist: {path}")
        else:
            return ProviderError()

    segments = file_comparison.segments

    if filters.get("has_unintended_changes") is True:
        segments = [segment for segment in segments if segment.has_unintended_changes]
    elif filters.get("has_unintended_changes") is False:
        segments = [
            segment for segment in segments if not segment.has_unintended_changes
        ]

    return SegmentComparisons(results=segments)


@impacted_file_bindable.field("segmentsDeprecated")
@sync_to_async
@convert_kwargs_to_snake_case
def resolve_segments_deprecated(
    impacted_file: ImpactedFile, info, filters=None
) -> List[Segment]:
    if filters is None:
        filters = {}
    if "comparison" not in info.context:
        return []

    comparison = info.context["comparison"]
    comparison.validate()
    file_comparison = comparison.get_file_comparison(
        impacted_file.head_name, with_src=True, bypass_max_diff=True
    )

    segments = file_comparison.segments

    if filters.get("has_unintended_changes") is True:
        segments = [segment for segment in segments if segment.has_unintended_changes]
    elif filters.get("has_unintended_changes") is False:
        segments = [
            segment for segment in segments if not segment.has_unintended_changes
        ]

    return segments


@impacted_file_bindable.field("isNewFile")
def resolve_is_new_file(impacted_file: ImpactedFile, info) -> bool:
    base_name = impacted_file.base_name
    head_name = impacted_file.head_name
    return base_name is None and head_name is not None


@impacted_file_bindable.field("isRenamedFile")
def resolve_is_renamed_file(impacted_file: ImpactedFile, info) -> bool:
    base_name = impacted_file.base_name
    head_name = impacted_file.head_name
    return base_name is not None and head_name is not None and base_name != head_name


@impacted_file_bindable.field("isDeletedFile")
def resolve_is_deleted_file(impacted_file: ImpactedFile, info) -> bool:
    base_name = impacted_file.base_name
    head_name = impacted_file.head_name
    return base_name is not None and head_name is None


@impacted_file_bindable.field("missesInComparison")
def resolve_misses_in_comparison(impacted_file: ImpactedFile, info) -> int:
    return impacted_file.misses_in_comparison


@impacted_file_bindable.field("isCriticalFile")
@sync_to_async
def resolve_is_critical_file(impacted_file: ImpactedFile, info) -> bool:
    if "profiling_summary" in info.context:
        base_name = impacted_file.base_name
        head_name = impacted_file.head_name

        profiling_summary: ProfilingSummary = info.context["profiling_summary"]
        critical_filenames = profiling_summary.critical_filenames

        return base_name in critical_filenames or head_name in critical_filenames
