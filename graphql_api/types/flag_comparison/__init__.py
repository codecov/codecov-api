from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import build_connection_graphql

from .flag_comparison import flag_comparison_bindable

flag_comparison = ariadne_load_local_graphql(__file__, "flag_comparison.graphql")
