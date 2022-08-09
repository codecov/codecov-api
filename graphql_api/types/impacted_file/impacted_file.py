from typing import List

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from services.comparison import Segment

impacted_file_bindable = ObjectType("ImpactedFile")
from compare.commands.compare.interactors.get_impacted_files import (
    ImpactedFileFromArchive,
)


@impacted_file_bindable.field("headName")
def resolve_head_name(impacted_file: ImpactedFileFromArchive, info) -> str:
    return impacted_file.head_name


@impacted_file_bindable.field("baseName")
def resolve_base_name(impacted_file: ImpactedFileFromArchive, info) -> str:
    return impacted_file.base_name


@impacted_file_bindable.field("headCoverage")
def resolve_head_coverage(impacted_file: ImpactedFileFromArchive, info) -> float:
    return impacted_file.head_coverage


@impacted_file_bindable.field("baseCoverage")
def resolve_base_coverage(impacted_file: ImpactedFileFromArchive, info) -> float:
    return impacted_file.base_coverage


@impacted_file_bindable.field("patchCoverage")
def resolve_patch_coverage(impacted_file: ImpactedFileFromArchive, info) -> float:
    return impacted_file.patch_coverage


@impacted_file_bindable.field("segments")
@sync_to_async
def resolve_segments(impacted_file: ImpactedFileFromArchive, info) -> List[Segment]:
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    comparison.validate()
    file_comparison = comparison.get_file_comparison(
        impacted_file.head_name, with_src=True, bypass_max_diff=True
    )
    return file_comparison.segments
