import datetime as dt
from math import floor

from django.db.models import (
    Aggregate,
    Avg,
    Case,
    F,
    FloatField,
    Func,
    Max,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast
from shared.django_apps.core.models import Repository
from shared.django_apps.reports.models import (
    DailyTestRollup,
    Flake,
)

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)

SLOW_TEST_PERCENTILE = 95


def slow_test_threshold(total_tests: int) -> int:
    percentile = (100 - SLOW_TEST_PERCENTILE) / 100
    slow_tests_to_return = floor(percentile * total_tests)
    return max(slow_tests_to_return, 1)


class ArrayLength(Func):
    function = "CARDINALITY"


class Unnest(Func):
    function = "unnest"


class Distinct(Func):
    function = "distinct"


class Array(Aggregate):
    function = "array"


class GENERATE_TEST_RESULT_PARAM:
    FLAKY = "flaky"
    FAILED = "failed"
    SLOWEST = "slowest"
    SKIPPED = "skipped"


def generate_test_results(
    repoid: int,
    branch: str | None = None,
    history: dt.timedelta | None = None,
    parameter: GENERATE_TEST_RESULT_PARAM | None = None,
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

    totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=time_ago)

    if branch is not None:
        totals = totals.filter(branch=branch)

    match parameter:
        case GENERATE_TEST_RESULT_PARAM.FLAKY:
            flakes = Flake.objects.filter(
                Q(repository_id=repoid)
                & (Q(end_date__date__isnull=True) | Q(end_date__date__gt=time_ago))
            )
            test_ids = [flake.test_id for flake in flakes]

            totals = totals.filter(test_id__in=test_ids)
        case GENERATE_TEST_RESULT_PARAM.FAILED:
            test_ids = (
                totals.values("test")
                .annotate(fail_count_sum=Sum("fail_count"))
                .filter(fail_count_sum__gt=0)
                .values("test_id")
            )

            totals = totals.filter(test_id__in=test_ids)
        case GENERATE_TEST_RESULT_PARAM.SKIPPED:
            test_ids = (
                totals.values("test")
                .annotate(
                    skip_count_sum=Sum("skip_count"),
                    fail_count_sum=Sum("fail_count"),
                    pass_count_sum=Sum("pass_count"),
                )
                .filter(skip_count_sum__gt=0, fail_count_sum=0, pass_count_sum=0)
                .values("test_id")
            )

            totals = totals.filter(test_id__in=test_ids)
        case GENERATE_TEST_RESULT_PARAM.SLOWEST:
            num_tests = totals.distinct("test_id").count()

            slowest_test_ids = (
                totals.values("test")
                .annotate(
                    runtime=Avg("avg_duration_seconds")
                    * (Sum("pass_count") + Sum("fail_count"))
                )
                .order_by("-runtime")
                .values("test_id")[0 : slow_test_threshold(num_tests)]
            )

            totals = totals.filter(test_id__in=slowest_test_ids)

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
        total_test_count=Cast(
            Sum(F("pass_count")),
            output_field=FloatField(),
        )
        + Cast(Sum(F("fail_count")), output_field=FloatField()),
        total_fail_count=Cast(Sum(F("fail_count")), output_field=FloatField()),
        total_flaky_fail_count=Cast(
            Sum(F("flaky_fail_count")), output_field=FloatField()
        ),
        failure_rate=Case(
            When(
                total_test_count=0,
                then=Value(0.0),
            ),
            default=F("total_fail_count") / F("total_test_count"),
        ),
        flake_rate=Case(
            When(
                total_test_count=0,
                then=Value(0.0),
            ),
            default=F("total_flaky_fail_count") / F("total_test_count"),
        ),
        updated_at=Max("latest_run"),
        commits_where_fail=ArrayLength(Array(Subquery(commits_where_fail_sq))),
        last_duration=Subquery(latest_duration_sq),
        avg_duration=Avg("avg_duration_seconds"),
        name=F("test__name"),
    )

    return aggregation_of_test_results


def percent_diff(numerator: int | float, denominator: int | float) -> int | float | None:
    if denominator == 0:
        return None
    return (numerator - denominator) / denominator * 100


def get_percent_change(
    fields: list[str],
    curr_numbers: dict[str, int | float],
    past_numbers: dict[str, int | float],
) -> dict[str, int | float]:
    percent_change_fields = {}

    for field in fields:
        if past_numbers.get(field):
            percent_change_fields[f"{field}_percent_change"] = percent_diff(
                curr_numbers[field], past_numbers[field]
            )

    return percent_change_fields


def get_test_results_aggregate_numbers(
    repo: Repository, since: dt.datetime, until: dt.datetime | None = None
) -> dict[str, float | int]:
    totals = DailyTestRollup.objects.filter(
        repoid=repo.repoid, date__gt=since, branch=repo.branch
    )

    if until:
        totals = totals.filter(date__lte=until)

    num_tests = totals.distinct("test_id").count()

    slowest_test_ids = (
        totals.values("test")
        .annotate(
            runtime=Sum(F("avg_duration_seconds") * (F("pass_count") + F("fail_count")))
            / Sum(F("pass_count") + F("fail_count"))
        )
        .order_by("-runtime")
        .values("test_id")[0 : slow_test_threshold(num_tests)]
    )

    slowest_tests_duration = (
        totals.filter(test_id__in=slowest_test_ids)
        .values("repoid")
        .annotate(
            slowest_tests=Sum(
                F("avg_duration_seconds") * (F("pass_count") + F("fail_count"))
            )
        )
        .values("slowest_tests")
    )

    test_headers = totals.values("repoid").annotate(
        total_run_time=Sum(
            F("avg_duration_seconds") * (F("pass_count") + F("fail_count"))
        ),
        slowest_tests_duration=slowest_tests_duration,
        skips=Sum("skip_count"),
        fails=Sum("fail_count"),
    )

    return test_headers[0] if len(test_headers) > 0 else {}


def generate_test_results_aggregates(
    repoid: int, history: dt.timedelta | None = None
) -> dict[str, float | int] | None:
    repo = Repository.objects.get(repoid=repoid)
    time_ago = (
        (dt.datetime.now(dt.UTC) - history) if history is not None else thirty_days_ago
    )

    curr_numbers = get_test_results_aggregate_numbers(repo, time_ago)

    double_time_ago = time_ago - (
        history if history is not None else dt.timedelta(days=30)
    )

    past_numbers = get_test_results_aggregate_numbers(repo, double_time_ago, time_ago)

    return curr_numbers | get_percent_change(
        ["total_run_time", "slowest_tests_duration", "skips", "fails"],
        curr_numbers,
        past_numbers,
    )


def get_flake_aggregate_numbers(
    repo: Repository, since: dt.datetime, until: dt.datetime | None = None
) -> dict[str, int | float]:
    if until is None:
        flakes = Flake.objects.filter(
            Q(repository_id=repo.repoid)
            & (Q(end_date__isnull=True) | Q(end_date__date__gt=since.date()))
        )
    else:
        flakes = Flake.objects.filter(
            Q(repository_id=repo.repoid)
            & ((Q(end_date__isnull=True)) | (Q(end_date__date__lte=until.date()) & Q(end_date__date__gt=since.date())))
        )

    flake_count = flakes.count()

    print("flake_count", flake_count)

    test_ids = [flake.test_id for flake in flakes]

    print("test_ids", test_ids)

    test_rollups = DailyTestRollup.objects.filter(
        repoid=repo.repoid,
        date__gt=since.date(),
        branch=repo.branch,
        test_id__in=test_ids,
    )
    if until:
        test_rollups = test_rollups.filter(date__lte=until.date())


    print("len(test_rollups)", len(test_rollups))

    if len(test_rollups) == 0:
        return {"flake_count": 0, "flake_rate": 0}

    numerator = 0
    denominator = 0
    for test_rollup in test_rollups:
        numerator += test_rollup.flaky_fail_count
        denominator += test_rollup.fail_count + test_rollup.pass_count

    if denominator == 0:
        flake_rate = 0.0
    else:
        flake_rate = numerator / denominator

    return {"flake_count": flake_count, "flake_rate": flake_rate}


def generate_flake_aggregates(
    repoid: int, history: dt.timedelta | None = None
) -> dict[str, int | float]:
    repo = Repository.objects.get(repoid=repoid)
    time_ago = (
        (dt.datetime.today() - history) if history is not None else thirty_days_ago
    )

    curr_numbers = get_flake_aggregate_numbers(repo, time_ago)

    double_time_ago = time_ago - (
        history if history is not None else dt.timedelta(days=30)
    )

    past_numbers = get_flake_aggregate_numbers(repo, double_time_ago, time_ago)

    return curr_numbers | get_percent_change(
        ["flake_count", "flake_rate"],
        curr_numbers,
        past_numbers,
    )
