from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .self_hosted_license import self_hosted_license_bindable

self_hosted_license = ariadne_load_local_graphql(
    __file__, "self_hosted_license.graphql"
)

__all__ = ["self_hosted_license", "self_hosted_license_bindable"]
