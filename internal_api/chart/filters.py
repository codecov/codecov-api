from django.db.models import Q, F
from django.db.models.functions import Trunc


def apply_default_filters(queryset):
    """
    By default we only want to include commits with meaningful coverage values when representing charts,
    so exclude from consideration commits where CI failed, commits that are still pending, etc.
    """
    return queryset.filter(
        state="complete", totals__isnull=False
    ).filter(Q(deleted__isnull=True) | Q(deleted=False))


def apply_simple_filters(queryset, data, user):
    """
    Apply any coverage chart filtering parameters that can be construed as a simple queryset.filter call.
    """

    queryset = queryset.annotate(
        trunc_timestamp=Trunc("timestamp", "day")
    ).filter(
        repository__author__username=data.get("owner_username") # filter by the organization in the request route
    ).filter(
        # make sure we only return repositories that are either public or that the logged-in user has permission to view.
        # this is important because if no "repository" param was provided then the permissions check will succeed, but we still
        # want to make sure we return only all repositories the logged-in user has permissions to view.
        Q(repository__private=False)
        | Q(repository__repoid__in=user.permission) 
    )

    # Handle branch filtering
    if data.get("branch"):
        queryset = queryset.filter(branch=data.get("branch"))
    else:
        # if no branch param was provided, default to filtering commits based on the repository's default branch
        queryset = queryset.filter(branch=F("repository__branch"))

    # Optional filters
    if data.get("repositories"):
        queryset = queryset.filter(repository__name__in=data.get("repositories", []))
    if data.get("start_date"):
        queryset = queryset.filter(trunc_timestamp__gte=data.get("start_date"))
    if data.get("end_date"):
        queryset = queryset.filter(trunc_timestamp__lte=data.get("end_date"))
    return queryset
