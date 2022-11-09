from typing import Iterable, Union

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


def sort_path_contents(
    items: Iterable[Union[File, Dir]], filters={}
) -> Iterable[Union[File, Dir]]:
    filter_parameter = filters.get("ordering", {}).get("parameter")
    filter_direction = filters.get("ordering", {}).get("direction")

    if filter_parameter and filter_direction:
        parameter_value = filter_parameter.value
        direction_value = filter_direction.value
        items = sorted(
            items,
            key=lambda item: getattr(item, parameter_value),
            reverse=direction_value == "descending",
        )
        if parameter_value == "name":
            (files, directories) = partition_list_into_files_and_directories(
                items=items
            )
            items = directories + files

    return items
