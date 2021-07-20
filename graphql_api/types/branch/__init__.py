from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .branch import branch_bindable

branch = ariadne_load_local_graphql(__file__, "branch.graphql")
