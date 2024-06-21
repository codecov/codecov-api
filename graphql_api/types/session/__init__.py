from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .session import session_bindable

session = ariadne_load_local_graphql(__file__, "session.graphql")

__all__ = ["session", "session_bindable"]
