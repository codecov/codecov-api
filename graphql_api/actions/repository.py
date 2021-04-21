from django.db.models.fields.json import KeyTransform

from core.models import Repository
from graphql_api.types.enums import RepositoryOrdering


def apply_ordering_annotations_to_queryset(queryset, ordering):
    if ordering == RepositoryOrdering.COVERAGE:
        queryset = queryset.annotate(
            coverage=KeyTransform(
                "c", KeyTransform("totals", KeyTransform("commit", "cache"))
            )
        )

    return queryset


def apply_filters_to_queryset(queryset, filters):
    filters = filters or {}
    term = filters.get("term")
    active = filters.get("active")
    if term:
        queryset = queryset.filter(name__contains=term)
    if active:
        queryset = queryset.filter(active=active)
    return queryset


def list_repository_for_owner(current_user, owner, filters, ordering):
    queryset = Repository.objects.viewable_repos(current_user).filter(author=owner)
    queryset = apply_filters_to_queryset(queryset, filters)
    queryset = apply_ordering_annotations_to_queryset(queryset, ordering)
    return queryset


def search_repos(current_user, filters, ordering):
    authors_from = [current_user.ownerid] + (current_user.organizations or [])
    queryset = Repository.objects.viewable_repos(current_user).filter(
        author__ownerid__in=authors_from
    )
    queryset = apply_filters_to_queryset(queryset, filters)
    queryset = apply_ordering_annotations_to_queryset(queryset, ordering)
    return queryset
