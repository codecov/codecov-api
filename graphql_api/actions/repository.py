import logging
from typing import Any

import sentry_sdk
from django.db.models import QuerySet
from shared.django_apps.codecov_auth.models import GithubAppInstallation, Owner
from shared.django_apps.core.models import Repository

from utils.config import get_config

log = logging.getLogger(__name__)
AI_FEATURES_GH_APP_ID = get_config("github", "ai_features_app_id")


def basic_filters(queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
    filters = filters or {}
    if repo_names := filters.get("repo_names"):
        queryset = queryset.filter(name__in=repo_names)
    if term := filters.get("term"):
        queryset = queryset.filter(name__contains=term)
    for field in ("activated", "active"):
        if filters.get(field) is not None:
            queryset = queryset.filter(**{field: filters[field]})
    if filters.get("is_public") is not None:
        queryset = queryset.filter(private=not filters["is_public"])
    return queryset


def filter_queryset_by_ai_enabled_repos(queryset: QuerySet, owner: Owner) -> QuerySet:
    install = GithubAppInstallation.objects.filter(
        app_id=AI_FEATURES_GH_APP_ID, owner=owner
    ).first()
    if not install:
        return Repository.objects.none()
    if install.repository_service_ids:
        queryset = queryset.filter(service_id__in=install.repository_service_ids)
    return queryset


def apply_filters(
    queryset: QuerySet, filters: dict[str, Any] | None, owner: Owner
) -> QuerySet:
    filters = filters or {}
    if filters.get("ai_enabled"):
        return filter_queryset_by_ai_enabled_repos(queryset, owner)
    return basic_filters(queryset, filters)


@sentry_sdk.trace
def list_repository_for_owner(
    current_owner: Owner,
    owner: Owner,
    filters: dict[str, Any] | None,
    okta_account_auths: list[int],
    exclude_okta_enforced_repos: bool = True,
) -> QuerySet:
    filters = filters or {}
    qs = Repository.objects.viewable_repos(current_owner)
    if filters.get("ai_enabled"):
        return filter_queryset_by_ai_enabled_repos(qs, owner)
    if exclude_okta_enforced_repos:
        qs = qs.exclude_accounts_enforced_okta(okta_account_auths)
    qs = qs.with_recent_coverage().with_latest_commit_at().filter(author=owner)
    return basic_filters(qs, filters)


@sentry_sdk.trace
def search_repos(
    current_owner: Owner,
    filters: dict[str, Any] | None,
    okta_account_auths: list[int],
    exclude_okta_enforced_repos: bool = True,
) -> QuerySet:
    filters = filters or {}
    authors = [current_owner.ownerid] + (current_owner.organizations or [])
    qs = Repository.objects.viewable_repos(current_owner)
    if exclude_okta_enforced_repos:
        qs = qs.exclude_accounts_enforced_okta(okta_account_auths)
    qs = (
        qs.with_recent_coverage()
        .with_latest_commit_at()
        .filter(author__ownerid__in=authors)
    )
    return apply_filters(qs, filters, current_owner)
