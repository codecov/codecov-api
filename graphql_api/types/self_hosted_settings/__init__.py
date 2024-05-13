from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .self_hosted_settings import self_hosted_settings_bindable

self_hosted_license = ariadne_load_local_graphql(
    __file__, "self_hosted_settings.graphql"
)
