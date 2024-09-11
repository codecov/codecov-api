from shared.license import get_current_license

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .account import account_bindable

account = ariadne_load_local_graphql(__file__, "account.graphql")


__all__ = ["get_current_license", "account_bindable"]
