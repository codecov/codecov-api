from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .path_content import (
    path_content_bindable,
    path_content_file_bindable,
    path_contents_result_bindable,
)

path_content = ariadne_load_local_graphql(__file__, "path_content.graphql")


__all__ = [
    "path_content",
    "path_content_bindable",
    "path_content_file_bindable",
    "path_contents_result_bindable",
]
