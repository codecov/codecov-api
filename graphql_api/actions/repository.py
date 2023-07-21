from codecov_auth.models import Owner
from core.models import Repository


def apply_filters_to_queryset(queryset, filters):
    filters = filters or {}
    term = filters.get("term")
    active = filters.get("active")
    activated = filters.get("activated")
    repo_names = filters.get("repo_names")

    if repo_names:
        queryset = queryset.filter(name__in=repo_names)
    if term:
        queryset = queryset.filter(name__contains=term)
    if activated is not None:
        queryset = queryset.filter(activated=activated)
    if active is not None:
        queryset = queryset.filter(active=active)
    return queryset


def list_repository_for_owner(current_owner: Owner, owner: Owner, filters):
    queryset = (
        Repository.objects.viewable_repos(current_owner)
        .with_recent_coverage()
        .with_cache_latest_commit_at()
        .filter(author=owner)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset


def search_repos(current_owner, filters):
    authors_from = [current_owner.ownerid] + (current_owner.organizations or [])
    queryset = (
        Repository.objects.viewable_repos(current_owner)
        .with_recent_coverage()
        .with_cache_latest_commit_at()
        .filter(author__ownerid__in=authors_from)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset
