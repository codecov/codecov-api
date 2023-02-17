from ariadne import load_schema_from_path
from ariadne_django.scalars import datetime_scalar

from ..helpers.ariadne import ariadne_load_local_graphql
from .branch import branch, branch_bindable
from .commit import commit, commit_bindable
from .comparison import comparison, comparison_bindable, comparison_result_bindable
from .component import component, component_bindable
from .component_comparison import component_comparison, component_comparison_bindable
from .config import config, config_bindable
from .coverage_totals import coverage_totals, coverage_totals_bindable
from .enums import enum_types, enums
from .file import commit_file, file_bindable
from .file_comparison import file_comparison, file_comparison_bindable
from .flag import flag, flag_bindable
from .flag_comparison import flag_comparison, flag_comparison_bindable
from .impacted_file import impacted_file, impacted_file_bindable
from .line_comparison import line_comparison, line_comparison_bindable
from .me import me, me_bindable, tracking_metadata_bindable
from .measurement import measurement, measurement_bindable
from .mutation import mutation, mutation_resolvers
from .owner import owner, owner_bindable
from .path_contents import (
    path_content,
    path_content_bindable,
    path_content_file_bindable,
    path_contents_result_bindable,
)
from .profile import profile, profile_bindable
from .pull import pull, pull_bindable
from .query import query, query_bindable
from .repository import repository, repository_bindable
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
from .session import session, session_bindable
from .upload import upload, upload_bindable, upload_error_bindable
from .user import user, user_bindable
from .user_token import user_token, user_token_bindable

inputs = ariadne_load_local_graphql(__file__, "./inputs")
enums = ariadne_load_local_graphql(__file__, "./enums")
errors = ariadne_load_local_graphql(__file__, "./errors")
types = [
    query,
    me,
    branch,
    commit,
    comparison,
    component,
    component_comparison,
    file_comparison,
    flag,
    flag_comparison,
    segment_comparison,
    line_comparison,
    measurement,
    pull,
    user,
    owner,
    repository,
    inputs,
    enums,
    session,
    mutation,
    errors,
    path_content,
    coverage_totals,
    upload,
    commit_file,
    profile,
    impacted_file,
    config,
    user_token,
    repository_config,
]

bindables = [
    query_bindable,
    me_bindable,
    branch_bindable,
    commit_bindable,
    comparison_bindable,
    comparison_result_bindable,
    component_bindable,
    component_comparison_bindable,
    file_comparison_bindable,
    flag_bindable,
    flag_comparison_bindable,
    segment_comparison_bindable,
    segments_result_bindable,
    line_comparison_bindable,
    measurement_bindable,
    pull_bindable,
    user_bindable,
    owner_bindable,
    repository_bindable,
    session_bindable,
    coverage_totals_bindable,
    file_bindable,
    upload_bindable,
    upload_error_bindable,
    path_content_bindable,
    path_content_file_bindable,
    datetime_scalar,
    profile_bindable,
    impacted_file_bindable,
    config_bindable,
    user_token_bindable,
    *mutation_resolvers,
    *enum_types.enum_types,
    path_contents_result_bindable,
    repository_config_bindable,
    indication_range_bindable,
    tracking_metadata_bindable,
]
