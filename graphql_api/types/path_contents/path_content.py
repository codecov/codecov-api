from typing import Union

from ariadne import InterfaceType, ObjectType

from services.path import Dir, File

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
def resolve_name(data: Union[File, Dir], info) -> str:
    return data.name


@path_content_bindable.field("path")
def resolve_file_path(data: Union[File, Dir], info) -> str:
    if data.kind == "file":
        return data.full_path
    return None


@path_content_bindable.field("percentCovered")
def resolve_percent_covered(data: Union[File, Dir], info) -> float:
    return data.coverage


@path_content_file_bindable.field("isCriticalFile")
def resolve_is_critical_file(data: File, info) -> bool:
    if "critical_filenames" in info.context:
        return data.full_path in info.context["critical_filenames"]

    return False
