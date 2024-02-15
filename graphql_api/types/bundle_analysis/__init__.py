from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .base import (
    bundle_asset_bindable,
    bundle_data_bindable,
    bundle_load_time_bindable,
    bundle_module_bindable,
    bundle_size_bindable,
)
from .comparison import (
    bundle_analysis_comparison_bindable,
    bundle_analysis_comparison_result_bindable,
    bundle_comparison_bindable,
)
from .report import (
    bundle_analysis_report_bindable,
    bundle_analysis_report_result_bindable,
    bundle_report_bindable,
)

bundle_analysis = ariadne_load_local_graphql(__file__, "base.graphql")
bundle_analysis_comparison = ariadne_load_local_graphql(__file__, "comparison.graphql")
bundle_analysis_report = ariadne_load_local_graphql(__file__, "report.graphql")
