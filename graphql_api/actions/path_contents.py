import sentry_sdk

from graphql_api.types.enums import PathContentDisplayType
from services.path import Dir, File


@sentry_sdk.trace
def sort_path_contents(items: list[File | Dir], filters: dict = {}) -> list[File | Dir]:
    filter_parameter = filters.get("ordering", {}).get("parameter")
    filter_direction = filters.get("ordering", {}).get("direction")

    if filter_parameter and filter_direction:
        parameter_value = filter_parameter.value
        direction_value = filter_direction.value
        items.sort(
            key=lambda item: getattr(item, parameter_value),
            reverse=direction_value == "descending",
        )
        display_type = filters.get("display_type", {})
        if (
            parameter_value == "name"
            and display_type is not PathContentDisplayType.LIST
        ):
            items.sort(key=lambda item: isinstance(item, File))

    return items
