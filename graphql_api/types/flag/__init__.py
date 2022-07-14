from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import build_connection_graphql

from .flag import flag_bindable

flag = ariadne_load_local_graphql(__file__, "flag.graphql")
flag += build_connection_graphql("FlagConnection", "Flag")
