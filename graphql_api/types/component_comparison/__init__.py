from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .component_comparison import component_comparison_bindable

component_comparison = ariadne_load_local_graphql(
    __file__, "component_comparison.graphql"
)
