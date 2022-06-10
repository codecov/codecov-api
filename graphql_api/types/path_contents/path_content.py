from typing import Union

from ariadne import ObjectType

from services.path import TreeDir, TreeFile

path_content_bindable = ObjectType("PathContent")


@path_content_bindable.field("name")
def resolve_name(data: Union[TreeFile, TreeDir], info) -> str:
    return data.name


@path_content_bindable.field("filePath")
def resolve_file_path(data: Union[TreeFile, TreeDir], info) -> str:
    if data.kind == "file":
        return data.full_path
    return None


@path_content_bindable.field("percentCovered")
def resolve_percent_covered(data: Union[TreeFile, TreeDir], info) -> float:
    return data.coverage


@path_content_bindable.field("type")
def resolve_type(data: Union[TreeFile, TreeDir], info) -> str:
    return data.kind
