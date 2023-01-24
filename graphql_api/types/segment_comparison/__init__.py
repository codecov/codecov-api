from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .segment_comparison import segment_comparison_bindable, segments_result_bindable

segment_comparison = ariadne_load_local_graphql(__file__, "segment_comparison.graphql")
