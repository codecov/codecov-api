from graphql_api.helpers.ariadne import ariadne_load_local_graphql


gql_create_api_token = ariadne_load_local_graphql(__file__, "create_api_token.graphql")


def resolve_create_api_token(_, info):
    return {}
