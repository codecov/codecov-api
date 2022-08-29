from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .regenerate_org_upload_token import (
    error_generate_org_upload_token,
    resolve_regenerate_org_upload_token,
)

gql_regenerate_org_upload_token = ariadne_load_local_graphql(
    __file__, "regenerate_org_upload_token.graphql"
)
