from typing import Iterable, Union

from services.path import Dir, File


def sort_path_contents(
    items: Iterable[Union[File, Dir]], filters
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

    return items
