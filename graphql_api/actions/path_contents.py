from typing import Iterable, Union

from graphql_api.types.enums import PathContentDisplayType
from services.path import Dir, File


def partition_list_into_files_and_directories(
    items: Iterable[Union[File, Dir]]
) -> tuple[Union[File, Dir]]:
    files = []
    directories = []

    # Separate files and directories
    for item in items:
        if type(item) == Dir:
            directories.append(item)
        else:
            files.append(item)

    return (files, directories)


def sort_list_by_directory(
    items: Iterable[Union[File, Dir]]
) -> Iterable[Union[File, Dir]]:
    (files, directories) = partition_list_into_files_and_directories(items=items)
    return directories + files


def sort_path_contents(
    items: Iterable[Union[File, Dir]], filters={}
) -> Iterable[Union[File, Dir]]:
    filter_parameter = filters.get("ordering", {}).get("parameter")
    filter_direction = filters.get("ordering", {}).get("direction")

    if filter_parameter and filter_direction:
        parameter_value = filter_parameter.value
        direction_value = filter_direction.value
        for item in items:
            print(getattr(item, "full_path"))
        items = sorted(
            items,
            key=lambda item: getattr(item, parameter_value),
            reverse=direction_value == "descending",
        )
        display_type = filters.get("display_type", {})
        if (
            parameter_value == "name"
            and display_type is not PathContentDisplayType.LIST
        ):
            items = sort_list_by_directory(items=items)

    return items
