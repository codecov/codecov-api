from django.db.models import FloatField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from core.models import Repository
from graphql_api.types.enums import RepositoryOrdering


def apply_filters_to_queryset(queryset, filters):
    filters = filters or {}
    term = filters.get("term")
    active = filters.get("active")
    repo_names = filters.get("repo_names")
    if repo_names:
        queryset = queryset.filter(name__in=repo_names)
    if term:
        queryset = queryset.filter(name__contains=term)
    if active is not None:
        queryset = queryset.filter(active=active)
    return queryset


def list_repository_for_owner(current_user, owner, filters):
    queryset = (
        Repository.objects.viewable_repos(current_user)
        .with_cache_coverage()
        .with_cache_latest_commit_at()
        .filter(author=owner)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset


def search_repos(current_user, filters):
    authors_from = [current_user.ownerid] + (current_user.organizations or [])
    queryset = (
        Repository.objects.viewable_repos(current_user)
        .with_cache_coverage()
        .with_cache_latest_commit_at()
        .filter(author__ownerid__in=authors_from)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset
