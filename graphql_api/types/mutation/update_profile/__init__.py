from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_profile import error_update_profile, resolve_update_profile

gql_update_profile = ariadne_load_local_graphql(__file__, "update_profile.graphql")
