from ariadne import load_schema_from_path
from ariadne.contrib.django.scalars import datetime_scalar

from ..helpers.ariadne import ariadne_load_local_graphql
from .query import query, query_bindable
from .me import me, me_bindable
from .branch import branch, branch_bindable
from .commit import commit, commit_bindable
from .comparison import comparison, comparison_bindable
from .upload import upload, upload_bindable
from .coverage_totals import coverage_totals, coverage_totals_bindable
from .user import user, user_bindable
from .owner import owner, owner_bindable
from .repository import repository, repository_bindable
from .session import session, session_bindable
from .file import commit_file
from .mutation import mutation, mutation_resolvers
from .enums import enums, enum_types

inputs = ariadne_load_local_graphql(__file__, "./inputs")
enums = ariadne_load_local_graphql(__file__, "./enums")
errors = ariadne_load_local_graphql(__file__, "./errors")
types = [
    query,
    me,
    branch,
    commit,
    comparison,
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
]

bindables = [
    query_bindable,
    me_bindable,
    branch_bindable,
    commit_bindable,
    comparison_bindable,
    user_bindable,
    owner_bindable,
    repository_bindable,
    session_bindable,
    coverage_totals_bindable,
    upload_bindable,
    datetime_scalar,
    *mutation_resolvers,
    *enum_types.enum_types,
]
