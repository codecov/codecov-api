import datetime as dt
from math import floor

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
from shared.django_apps.core.models import Repository
from shared.django_apps.reports.models import DailyTestRollup, TestInstance

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)

SLOW_TEST_PERCENTILE = 95


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
    The fields it calculates are: the test failure rate, commits where this test failed, last duration and average duration of the test.

    :param repoid: repoid of the repository we want to calculate aggregates for
    :param branch: optional name of the branch we want to filter on, if this is provided the aggregates calculated will only take into account test instances generated on that branch. By default branches will not be filtered and test instances on all branches wil be taken into account.
    :param history: optional timedelta field for filtering test instances used to calculated the aggregates by time, the test instances used will be those with a created at larger than now - history.
    :returns: queryset object containing list of dictionaries of results

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

    return aggregation_of_test_results


def test_results_headers(
    repoid: int, history: dt.timedelta | None = None
) -> dict[str, float | int] | None:
    repo = Repository.objects.get(repoid=repoid)
    time_ago = (
        (dt.datetime.now(dt.UTC) - history) if history is not None else thirty_days_ago
    )

    totals = DailyTestRollup.objects.filter(
        repoid=repoid, date__gt=time_ago, branch=repo.branch
    )

    num_tests = totals.distinct("test_id").count()

    slow_test_threshold = floor(num_tests * (100 - SLOW_TEST_PERCENTILE) * 0.01)

    if slow_test_threshold == 0:
        if num_tests == 1:
            slow_test_threshold = 1
        else:
            return None

    slowest_test_ids = (
        totals.values("test")
        .annotate(
            runtime=Avg("avg_duration_seconds")
            * (Sum("pass_count") + Sum("fail_count"))
        )
        .order_by("-runtime")
        .values("test_id")[0:slow_test_threshold]
    )

    slowest_tests_duration = (
        totals.filter(test_id__in=slowest_test_ids)
        .values("repoid")
        .annotate(
            slowest_tests=Avg("avg_duration_seconds")
            * (Sum("pass_count") + Sum("fail_count"))
        )
        .values("slowest_tests")
    )

    test_headers = totals.values("repoid").annotate(
        total_run_time=Avg("avg_duration_seconds")
        * (Sum("pass_count") + Sum("fail_count")),
        slowest_tests_duration=slowest_tests_duration,
        skips=Sum("skip_count"),
        fails=Sum("fail_count"),
    )

    if test_headers:
        return test_headers[0]
    else:
        return None
