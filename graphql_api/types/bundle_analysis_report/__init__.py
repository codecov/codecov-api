from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .bundle_analysis_report import (
    bundle_analysis_report_bindable,
    bundle_analysis_report_result_bindable,
    bundle_report_bindable,
)

bundle_analysis_report = ariadne_load_local_graphql(
    __file__, "bundle_analysis_report.graphql"
)
