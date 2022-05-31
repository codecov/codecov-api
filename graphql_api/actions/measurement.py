import operator
from functools import reduce

from asgiref.sync import sync_to_async
from django.db.models import Avg, Max, Min, Q
from django.db.models.query import QuerySet

from codecov_auth.models import Owner
from core.models import Repository
from timeseries.models import Interval, MeasurementSummary


@sync_to_async
def measurement_queryset(
    current_user: Owner,
    owner: Owner,
    name: str,
    interval: Interval,
    filters: list,
) -> QuerySet:
    repo_ids = list(
        Repository.objects.viewable_repos(current_user)
        .filter(author=owner)
        .values_list("pk", flat=True)
    )

    queryset = MeasurementSummary.agg_by(interval).filter(
        name=name, owner_id=owner.pk, repo_id__in=repo_ids
    )

    querysets = [filter_queryset(queryset, filter) for filter in filters]

    # force eager execution of query while we're in a sync context
    return [list(queryset) for queryset in querysets]


def filter_queryset(queryset: QuerySet, filter: dict) -> QuerySet:
    queryset = queryset.filter(
        timestamp_bin__gte=filter["after"],
        timestamp_bin__lte=filter["before"],
    )

    conditions = []
    if "repo_id" in filter:
        conditions.append(Q(repo_id=filter["repo_id"]))
    if "branch" in filter:
        conditions.append(Q(branch=filter["branch"]))
    if "flag_id" in filter:
        conditions.append(Q(flag_id=filter["flag_id"]))

    if len(conditions) > 0:
        queryset = queryset.filter(reduce(operator.and_, conditions))

    # We'll only return a single set of values per timestamp so group by "timestamp_bin".
    # If the above conditions do not select a unique set of measurements then the results
    # will be aggregated across missing filter conditions.
    return (
        queryset.values("timestamp_bin")
        .annotate(
            avg=Avg("value_avg"),
            min=Min("value_min"),
            max=Max("value_max"),
        )
        .order_by("timestamp_bin")
    )
