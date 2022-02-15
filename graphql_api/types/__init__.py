from ariadne import load_schema_from_path
from ariadne_django.scalars import datetime_scalar

from ..helpers.ariadne import ariadne_load_local_graphql
from .branch import branch, branch_bindable
from .commit import commit, commit_bindable
from .comparison import comparison, comparison_bindable
from .coverage_totals import coverage_totals, coverage_totals_bindable
from .enums import enum_types, enums
from .file import commit_file, file_bindable
from .me import me, me_bindable
from .mutation import mutation, mutation_resolvers
from .owner import owner, owner_bindable
from .profile import profile, profile_bindable
from .pull import pull, pull_bindable
from .query import query, query_bindable
from .repository import repository, repository_bindable
from .session import session, session_bindable
from .upload import upload, upload_bindable, upload_error_bindable
from .user import user, user_bindable

inputs = ariadne_load_local_graphql(__file__, "./inputs")
enums = ariadne_load_local_graphql(__file__, "./enums")
errors = ariadne_load_local_graphql(__file__, "./errors")
types = [
    query,
    me,
    branch,
    commit,
    comparison,
    pull,
    user,
    owner,
    repository,
    inputs,
    enums,
    session,
    mutation,
    errors,
    coverage_totals,
    upload,
    commit_file,
    profile,
]

bindables = [
    query_bindable,
    me_bindable,
    branch_bindable,
    commit_bindable,
    comparison_bindable,
    pull_bindable,
    user_bindable,
    owner_bindable,
    repository_bindable,
    session_bindable,
    coverage_totals_bindable,
    file_bindable,
    upload_bindable,
    upload_error_bindable,
    datetime_scalar,
    profile_bindable,
    *mutation_resolvers,
    *enum_types.enum_types,
]
