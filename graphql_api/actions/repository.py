import logging
from typing import Any

from django.db.models import QuerySet
from shared.django_apps.codecov_auth.models import Owner
from shared.django_apps.core.models import Repository

log = logging.getLogger(__name__)


def apply_filters_to_queryset(queryset, filters: dict[str, Any]) -> QuerySet:
    filters = filters or {}
    term = filters.get("term")
    active = filters.get("active")
    activated = filters.get("activated")
    repo_names = filters.get("repo_names")
    is_public = filters.get("is_public")

    if repo_names:
        queryset = queryset.filter(name__in=repo_names)
    if term:
        queryset = queryset.filter(name__contains=term)
    if activated is not None:
        queryset = queryset.filter(activated=activated)
    if active is not None:
        queryset = queryset.filter(active=active)
    if is_public is not None:
        queryset = queryset.filter(private=not is_public)

    return queryset


def list_repository_for_owner(
    current_owner: Owner,
    owner: Owner,
    filters: dict[str, Any] | None,
    okta_account_auths: list[int],
) -> QuerySet:
    queryset = (
        Repository.objects.viewable_repos(current_owner)
        .exclude_accounts_enforced_okta(okta_account_auths)
        .with_recent_coverage()
        .with_latest_commit_at()
        .filter(author=owner)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset


def search_repos(
    current_owner: Owner, filters: dict[str, Any] | None, okta_account_auths: list[int]
) -> QuerySet:
    authors_from = [current_owner.ownerid] + (current_owner.organizations or [])
    queryset = (
        Repository.objects.viewable_repos(current_owner)
        .exclude_accounts_enforced_okta(okta_account_auths)
        .with_recent_coverage()
        .with_latest_commit_at()
        .filter(author__ownerid__in=authors_from)
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset
