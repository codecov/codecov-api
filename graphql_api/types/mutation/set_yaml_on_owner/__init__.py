from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .set_yaml_on_owner import error_set_yaml_error, resolve_set_yaml_on_owner

gql_set_yaml_on_owner = ariadne_load_local_graphql(
    __file__, "set_yaml_on_owner.graphql"
)
