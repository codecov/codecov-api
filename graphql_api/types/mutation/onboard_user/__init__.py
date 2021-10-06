from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .onboard_user import resolve_onboard_user, error_onboard_user


gql_onboard_user = ariadne_load_local_graphql(__file__, "onboard_user.graphql")
