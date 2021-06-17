from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .coverage_totals import coverage_totals_bindable

coverage_totals = ariadne_load_local_graphql(__file__, "coverage_totals.graphql")
