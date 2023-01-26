from typing import List, Union

from ariadne import InterfaceType, ObjectType, UnionType
from asgiref.sync import sync_to_async

from graphql_api.types.errors import MissingCoverage, MissingHeadReport, UnknownPath
from services.path import Dir, File
from services.profiling import ProfilingSummary

path_content_bindable = InterfaceType("PathContent")
path_content_file_bindable = ObjectType("PathContentFile")


@path_content_bindable.type_resolver
def resolve_path_content_type(obj, *_):
    if isinstance(obj, File):
        return "PathContentFile"
    if isinstance(obj, Dir):
        return "PathContentDir"
    return None


@path_content_bindable.field("name")
def resolve_name(item: Union[File, Dir], info) -> str:
    return item.name


@path_content_bindable.field("path")
def resolve_file_path(item: Union[File, Dir], info) -> str:
    return item.full_path


@path_content_bindable.field("hits")
def resolve_hits(item: Union[File, Dir], info) -> int:
    return item.hits


@path_content_bindable.field("misses")
def resolve_misses(item: Union[File, Dir], info) -> int:
    return item.misses


@path_content_bindable.field("partials")
def resolve_partials(item: Union[File, Dir], info) -> int:
    return item.partials


@path_content_bindable.field("lines")
def resolve_lines(item: Union[File, Dir], info) -> int:
    return item.lines


@path_content_bindable.field("percentCovered")
def resolve_percent_covered(item: Union[File, Dir], info) -> float:
    return item.coverage


@path_content_file_bindable.field("isCriticalFile")
@sync_to_async
def resolve_is_critical_file(item: Union[File, Dir], info) -> bool:
    if isinstance(item, File) and "profiling_summary" in info.context:
        profiling_summary: ProfilingSummary = info.context["profiling_summary"]
        return item.full_path in profiling_summary.critical_filenames

    return False


path_contents_result_bindable = UnionType("PathContentsResult")


@path_contents_result_bindable.type_resolver
def resolve_path_contents_result_type(res, *_):
    if isinstance(res, MissingHeadReport):
        return "MissingHeadReport"
    elif isinstance(res, MissingCoverage):
        return "MissingCoverage"
    elif isinstance(res, UnknownPath):
        return "UnknownPath"
    if isinstance(res, type({"results": List[Union[File, Dir]]})):
        return "PathContents"
