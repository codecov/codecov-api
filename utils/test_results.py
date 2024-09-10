import datetime as dt
from dataclasses import dataclass

from django.db.models import (
    Aggregate,
    Avg,
    F,
    FloatField,
    Func,
    Max,
    OuterRef,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Cast
from shared.django_apps.reports.models import DailyTestRollup, TestInstance

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)


@dataclass
class TestResultsAggregation:
    failure_rate: float | None
    commits_where_fail: list[str] | None
    average_duration: float | None


class ArrayLength(Func):
    function = "CARDINALITY"


class Unnest(Func):
    function = "unnest"


class Distinct(Func):
    function = "distinct"


class Array(Aggregate):
    function = "array"


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
        (dt.datetime.now(dt.UTC) - history) if history is not None else thirty_days_ago
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

    totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=time_ago)

    print([(t.pass_count, t.fail_count) for t in totals], branch)

    if branch is not None:
        totals = totals.filter(branch=branch)

    commits_where_fail_sq = (
        totals.filter(test_id=OuterRef("test_id"))
        .annotate(v=Distinct(Unnest(F("commits_where_fail"))))
        .values("v")
    )
    latest_duration_sq = (
        totals.filter(test_id=OuterRef("test_id"))
        .values("last_duration_seconds")
        .order_by("-latest_run")[:1]
    )

    aggregation_of_test_results = totals.values("test").annotate(
        failure_rate=(
            Cast(Sum(F("fail_count")), output_field=FloatField())
            / (
                Cast(
                    Sum(F("pass_count")),
                    output_field=FloatField(),
                )
                + Cast(Sum(F("fail_count")), output_field=FloatField())
            )
        ),
        updated_at=Max("latest_run"),
        commits_where_fail=ArrayLength(Array(Subquery(commits_where_fail_sq))),
        last_duration=Subquery(latest_duration_sq),
        avg_duration=Avg("avg_duration_seconds"),
        name=F("test__name"),
    )

    print(aggregation_of_test_results.query)

    return aggregation_of_test_results
