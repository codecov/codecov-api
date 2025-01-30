from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .billing import billing_bindable

billing = ariadne_load_local_graphql(__file__, "billing.graphql")


__all__ = ["billing_bindable"]
