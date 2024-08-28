import datetime as dt
from dataclasses import dataclass

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import (
    Avg,
    Case,
    F,
    FloatField,
    Func,
    IntegerField,
    Max,
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from shared.django_apps.reports.models import TestInstance

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)


@dataclass
class TestResultsAggregation:
    failure_rate: float | None
    commits_where_fail: list[str] | None
    average_duration: float | None


class ArrayLength(Func):
    function = "CARDINALITY"


def aggregate_test_results(
    repoid: int,
    branch: str | None = None,
    history: dt.timedelta | None = None,
) -> QuerySet:
    """
    Function that retrieves aggregated information about all tests in a given repository, for a given time range, optionally filtered by branch name.
    The fields it calculates are: the test failure rate, commits where this test failed, and average duration of the test.

    :param repoid: repoid of the repository we want to calculate aggregates for
    :param branch: optional name of the branch we want to filter on, if this is provided the aggregates calculated will only take into account test instances generated on that branch. By default branches will not be filtered and test instances on all branches wil be taken into account.
    :param history: optional timedelta field for filtering test instances used to calculated the aggregates by time, the test instances used will be those with a created at larger than now - history.
    :returns: dictionary mapping test id to dictionary containing

    """
    time_ago = (
        dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
        if history is not None
        else thirty_days_ago
    )

    pass_failure_error_test_instances = TestInstance.objects.filter(
        repoid=repoid,
        created_at__gt=time_ago,
        outcome__in=["pass", "failure", "error"],
    )

    if branch is not None:
        pass_failure_error_test_instances = pass_failure_error_test_instances.filter(
            branch=branch
        )

    failure_rates_queryset = (
        pass_failure_error_test_instances.values("test")
        .annotate(
            failure_rate=Avg(
                Case(
                    When(outcome="pass", then=Value(0.0)),
                    When(outcome__in=["failure", "error"], then=Value(1.0)),
                    output_field=FloatField(),
                )
            ),
            updated_at=Max("created_at"),
            commits_where_fail=Coalesce(
                ArrayLength(
                    ArrayAgg(
                        "commitid",
                        distinct=True,
                        filter=Q(outcome__in=["failure", "error"]),
                    )
                ),
                0,
                output_field=IntegerField(),
            ),
            avg_duration=Avg("duration_seconds"),
            name=F("test__name"),
        )
        .values(
            "failure_rate",
            "commits_where_fail",
            "avg_duration",
            "name",
            "updated_at",
        )
    )

    return failure_rates_queryset
