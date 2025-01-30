from ariadne.validation import cost_directive
from ariadne_django.scalars import datetime_scalar

from ..helpers.ariadne import ariadne_load_local_graphql
from .account import account, account_bindable
from .billing import billing, billing_bindable
from .branch import branch, branch_bindable
from .bundle_analysis import (
    bundle_analysis,
    bundle_analysis_comparison,
    bundle_analysis_comparison_bindable,
    bundle_analysis_comparison_result_bindable,
    bundle_analysis_report,
    bundle_analysis_report_bindable,
    bundle_analysis_report_result_bindable,
    bundle_asset_bindable,
    bundle_comparison_bindable,
    bundle_data_bindable,
    bundle_module_bindable,
    bundle_report_bindable,
    bundle_report_info_bindable,
)
from .commit import (
    commit,
    commit_bindable,
    commit_bundle_analysis_bindable,
    commit_coverage_analytics_bindable,
)
from .comparison import comparison, comparison_bindable, comparison_result_bindable
from .component import component, component_bindable
from .component_comparison import component_comparison, component_comparison_bindable
from .config import config, config_bindable
from .coverage_analytics import coverage_analytics, coverage_analytics_bindable
from .coverage_totals import coverage_totals, coverage_totals_bindable
from .enums import enum_types
from .file import commit_file, file_bindable
from .flag import flag, flag_bindable
from .flag_comparison import flag_comparison, flag_comparison_bindable
from .flake_aggregates import flake_aggregates, flake_aggregates_bindable
from .impacted_file import (
    impacted_file,
    impacted_file_bindable,
    impacted_files_result_bindable,
)
from .invoice import invoice, invoice_bindable
from .line_comparison import line_comparison, line_comparison_bindable
from .me import me, me_bindable, tracking_metadata_bindable
from .measurement import measurement, measurement_bindable
from .mutation import mutation, mutation_resolvers
from .okta_config import okta_config, okta_config_bindable
from .owner import owner, owner_bindable
from .path_contents import (
    deprecated_path_contents_result_bindable,
    path_content,
    path_content_bindable,
    path_content_file_bindable,
    path_contents_result_bindable,
)
from .plan import plan, plan_bindable
from .plan_representation import plan_representation, plan_representation_bindable
from .profile import profile, profile_bindable
from .pull import pull, pull_bindable
from .query import query, query_bindable
from .repository import repository, repository_bindable, repository_result_bindable
from .repository_config import (
    indication_range_bindable,
    repository_config,
    repository_config_bindable,
)
from .segment_comparison import (
    segment_comparison,
    segment_comparison_bindable,
    segments_result_bindable,
)
from .self_hosted_license import self_hosted_license, self_hosted_license_bindable
from .session import session, session_bindable
from .test_analytics import test_analytics, test_analytics_bindable
from .test_results import test_result_bindable, test_results
from .test_results_aggregates import (
    test_results_aggregates,
    test_results_aggregates_bindable,
)
from .upload import upload, upload_bindable, upload_error_bindable
from .user import user, user_bindable
from .user_token import user_token, user_token_bindable

inputs = ariadne_load_local_graphql(__file__, "./inputs")
enums = ariadne_load_local_graphql(__file__, "./enums")
errors = ariadne_load_local_graphql(__file__, "./errors")
types = [
    billing,
    branch,
    bundle_analysis_comparison,
    bundle_analysis_report,
    bundle_analysis,
    commit_file,
    commit,
    comparison,
    component_comparison,
    component,
    config,
    cost_directive,
    coverage_analytics,
    coverage_totals,
    enums,
    errors,
    flag_comparison,
    flag,
    impacted_file,
    inputs,
    invoice,
    line_comparison,
    me,
    measurement,
    mutation,
    owner,
    path_content,
    plan_representation,
    plan,
    profile,
    pull,
    query,
    repository_config,
    repository,
    segment_comparison,
    self_hosted_license,
    session,
    test_analytics,
    upload,
    user_token,
    user,
    account,
    okta_config,
    test_results,
    flake_aggregates,
    test_results_aggregates,
]

bindables = [
    *enum_types.enum_types,
    *mutation_resolvers,
    billing_bindable,
    branch_bindable,
    bundle_analysis_comparison_bindable,
    bundle_analysis_comparison_result_bindable,
    bundle_analysis_report_bindable,
    bundle_analysis_report_result_bindable,
    bundle_asset_bindable,
    bundle_comparison_bindable,
    bundle_data_bindable,
    bundle_module_bindable,
    bundle_report_bindable,
    bundle_report_info_bindable,
    commit_bindable,
    commit_bundle_analysis_bindable,
    commit_coverage_analytics_bindable,
    comparison_bindable,
    comparison_result_bindable,
    component_bindable,
    component_comparison_bindable,
    config_bindable,
    coverage_analytics_bindable,
    coverage_totals_bindable,
    datetime_scalar,
    file_bindable,
    flag_bindable,
    flag_comparison_bindable,
    impacted_file_bindable,
    impacted_files_result_bindable,
    indication_range_bindable,
    invoice_bindable,
    line_comparison_bindable,
    me_bindable,
    measurement_bindable,
    owner_bindable,
    path_content_bindable,
    path_content_file_bindable,
    path_contents_result_bindable,
    deprecated_path_contents_result_bindable,
    plan_bindable,
    plan_representation_bindable,
    profile_bindable,
    pull_bindable,
    query_bindable,
    repository_bindable,
    repository_config_bindable,
    repository_result_bindable,
    segment_comparison_bindable,
    segments_result_bindable,
    self_hosted_license_bindable,
    session_bindable,
    test_analytics_bindable,
    tracking_metadata_bindable,
    upload_bindable,
    upload_error_bindable,
    user_bindable,
    user_token_bindable,
    account_bindable,
    okta_config_bindable,
    test_result_bindable,
    test_results_aggregates_bindable,
    flake_aggregates_bindable,
]
