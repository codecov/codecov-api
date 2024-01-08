from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .bundle_analysis_comparison import (
    bundle_analysis_comparison_bindable,
    bundle_analysis_comparison_result_bindable,
    bundle_comparison_bindable,
)

bundle_analysis_comparison = ariadne_load_local_graphql(
    __file__, "bundle_analysis_comparison.graphql"
)
