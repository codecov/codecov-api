from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .coverage_diff import coverage_diff_bindable

coverage_diff = ariadne_load_local_graphql(__file__, "coverage_diff.graphql")
