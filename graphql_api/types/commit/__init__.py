from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .commit import commit_bindable

commit = ariadne_load_local_graphql(__file__, "commit.graphql")


__all__ = ["commit_bindable"]
