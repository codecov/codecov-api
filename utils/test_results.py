import datetime as dt
from base64 import b64decode, b64encode
from collections import defaultdict
from dataclasses import dataclass
from math import floor

from django.db import connection
from django.db.models import (
    Aggregate,
    Avg,
    F,
    Func,
    Q,
    Sum,
    Value,
)
from shared.django_apps.core.models import Repository
from shared.django_apps.reports.models import (
    DailyTestRollup,
    Flake,
    TestFlagBridge,
)

from codecov.commands.exceptions import ValidationError
from graphql_api.types.enums.enums import OrderingDirection

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


@dataclass
class TestResultsQuery:
    query: str
    params: dict[str, int | str | tuple[str, ...]]


def convert_tuple_or_none(value: set[str] | list[str] | None) -> tuple[str, ...] | None:
    return tuple(value) if value else None


def encode_after_or_before(value: str | None) -> str | None:
    return str(b64decode(value.encode("ascii"))) if value else None


def generate_base_query(
    repoid: int,
    ordering: tuple[str, ...],
    ordering_direction: OrderingDirection,
    first: int | None,
    after: str | None,
    last: int | None,
    before: str | None,
    branch: str | None,
    interval_num_days: int,
    testsuites: list[str] | None = None,
    term: str | None = None,
    test_ids: set[str] | None = None,
) -> TestResultsQuery:
    page_size = first or last

    term_filter = f"%{term}%" if term else None

    if interval_num_days not in {1, 7, 30}:
        raise ValueError(f"Invalid interval: {interval_num_days}")

    if ordering_direction not in {OrderingDirection.ASC, OrderingDirection.DESC}:
        raise ValueError(f"Invalid ordering direction: {ordering_direction}")

    for order_field in ordering:
        if order_field not in {
            "name",
            "computed_name",
            "avg_duration",
            "failure_rate",
            "flake_rate",
            "commits_where_fail",
            "last_duration",
        }:
            raise ValueError(f"Invalid ordering field: {order_field}")

    order = ",".join(
        [
            f"rt.{order_field}"
            if order_field in {"name", "computed_name"}
            else f"results.{order_field}"
            for order_field in ordering
        ]
    )
    order_by = ",".join(
        [f"with_cursor.{order} {ordering_direction.name}" for order in ordering]
    )

    params: dict[str, int | str | tuple[str, ...] | None] = {
        "repoid": repoid,
        "interval": f"{interval_num_days} days",
        "branch": branch,
        "test_ids": convert_tuple_or_none(test_ids),
        "testsuites": convert_tuple_or_none(testsuites),
        "term": term_filter,
        "after": encode_after_or_before(after),
        "before": encode_after_or_before(before),
        "limit": page_size,
    }
    filtered_params: dict[str, int | str | tuple[str, ...]] = {
        k: v for k, v in params.items() if v is not None
    }

    base_query = f"""
with
base_cte as (
	select rd.*
	from reports_dailytestrollups rd
    { "join reports_test rt on rt.id = rd.test_id" if testsuites or term else ""}
	where
        rd.repoid = %(repoid)s
		and rd.date > current_date - interval %(interval)s
        { "and rd.branch = %(branch)s" if branch else ""}
        { "and rd.test_id in %(test_ids)s" if test_ids else ""}
        { "and rt.testsuite in %(testsuites)s" if testsuites else ""}
        { "and rt.name like %(term)s" if term else ""}
),
failure_rate_cte as (
	select
		test_id,
		CASE
			WHEN SUM(pass_count) + SUM(fail_count) = 0 THEN 0
			ELSE SUM(fail_count)::float / (SUM(pass_count) + SUM(fail_count))
		END as failure_rate,
		CASE
			WHEN SUM(pass_count) + SUM(fail_count) = 0 THEN 0
			ELSE SUM(flaky_fail_count)::float / (SUM(pass_count) + SUM(fail_count))
		END as flake_rate,
		MAX(latest_run) as updated_at,
		AVG(avg_duration_seconds) AS avg_duration,
        SUM(fail_count) as total_fail_count,
        SUM(pass_count) as total_pass_count,
        SUM(skip_count) as total_skip_count
	from base_cte
	group by test_id
),
commits_where_fail_cte as (
	select test_id, array_length((array_agg(distinct unnested_cwf)), 1) as failed_commits_count from (
		select test_id, commits_where_fail as cwf
		from base_cte
		where array_length(commits_where_fail,1) > 0
	) as foo, unnest(cwf) as unnested_cwf group by test_id
),
last_duration_cte as (
	select base_cte.test_id, last_duration_seconds from base_cte
	join (
		select
			test_id,
			max(created_at) as created_at
		from base_cte
		group by test_id
	) as latest_rollups
    on base_cte.created_at = latest_rollups.created_at
)

select * from (
    select
    rt.name,
    rt.computed_name,
    results.*,
    row({order}) as _cursor
    from
    (
        select failure_rate_cte.*, coalesce(commits_where_fail_cte.failed_commits_count, 0) as commits_where_fail, last_duration_cte.last_duration_seconds as last_duration
        from failure_rate_cte
        full outer join commits_where_fail_cte using (test_id)
        full outer join last_duration_cte using (test_id)
    ) as results join reports_test rt on results.test_id = rt.id
) as with_cursor
{"where with_cursor._cursor > %(before)s" if after else ""}
{"where with_cursor._cursor < %(after)s" if before else ""}
order by {order_by}
limit %(limit)s
"""
    return TestResultsQuery(query=base_query, params=filtered_params)


@dataclass
class TestResultsRow:
    name: str
    computed_name: str
    test_id: str
    failure_rate: float
    flake_rate: float
    updated_at: dt.datetime
    avg_duration: float
    total_fail_count: int
    total_pass_count: int
    total_skip_count: int
    commits_where_fail: int
    last_duration: float


@dataclass
class Connection:
    edges: list[dict[str, str | TestResultsRow]]
    page_info: dict
    total_count: int


def get_cursor(row: TestResultsRow, ordering: tuple[str, ...]) -> str:
    return b64encode(
        "|".join([str(getattr(row, order)) for order in ordering]).encode("utf8")
    ).decode("ascii")


def generate_test_results(
    ordering: tuple[str, ...],
    ordering_direction: OrderingDirection,
    repoid: int,
    interval: dt.timedelta,
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
    branch: str | None = None,
    parameter: GENERATE_TEST_RESULT_PARAM | None = None,
    testsuites: list[str] | None = None,
    flags: defaultdict[str, str] | None = None,
    term: str | None = None,
) -> Connection | ValidationError:
    """
    Function that retrieves aggregated information about all tests in a given repository, for a given time range, optionally filtered by branch name.
    The fields it calculates are: the test failure rate, commits where this test failed, last duration and average duration of the test.

    :param repoid: repoid of the repository we want to calculate aggregates for
    :param branch: optional name of the branch we want to filter on, if this is provided the aggregates calculated will only take into account
        test instances generated on that branch. By default branches will not be filtered and test instances on all branches wil be taken into
        account.
    :param interval: timedelta for filtering test instances used to calculated the aggregates by time, the test instances used will be
        those with a created at larger than now - interval.
    :param testsuites: optional list of testsuite names to filter by
    :param flags: optional list of flag names to filter by, this is done via a union so if a user specifies multiple flags, we get all tests with any
        of the flags, not tests that have all of the flags
    :returns: queryset object containing list of dictionaries of results

    """
    interval_num_days = interval.days
    since = dt.datetime.now(dt.UTC) - interval

    test_ids: set[str] | None = None

    if flags is not None:
        bridges = TestFlagBridge.objects.select_related("flag").filter(
            flag__flag_name__in=flags
        )

        test_ids = set([bridge.test_id for bridge in bridges])

    if term is not None:
        totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)

        totals = totals.filter(test__name__icontains=term).values("test_id")

        filtered_test_ids = set([test["test_id"] for test in totals])

        test_ids = test_ids & filtered_test_ids if test_ids else filtered_test_ids

    if parameter is not None:
        totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)

        match parameter:
            case GENERATE_TEST_RESULT_PARAM.FLAKY:
                flakes = Flake.objects.filter(
                    Q(repository_id=repoid)
                    & (Q(end_date__date__isnull=True) | Q(end_date__date__gt=since))
                )

                flaky_test_ids = set([flake.test_id for flake in flakes])

                test_ids = test_ids & flaky_test_ids if test_ids else flaky_test_ids
            case GENERATE_TEST_RESULT_PARAM.FAILED:
                totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)

                failed_test_ids = (
                    totals.values("test")
                    .annotate(fail_count_sum=Sum("fail_count"))
                    .filter(fail_count_sum__gt=0)
                    .values("test_id")
                )
                failed_test_id_set = {test["test_id"] for test in failed_test_ids}

                test_ids = (
                    test_ids & failed_test_id_set if test_ids else failed_test_id_set
                )
            case GENERATE_TEST_RESULT_PARAM.SKIPPED:
                totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)

                skipped_test_ids = (
                    totals.values("test")
                    .annotate(
                        skip_count_sum=Sum("skip_count"),
                        fail_count_sum=Sum("fail_count"),
                        pass_count_sum=Sum("pass_count"),
                    )
                    .filter(skip_count_sum__gt=0, fail_count_sum=0, pass_count_sum=0)
                    .values("test_id")
                )
                skipped_test_id_set = {test["test_id"] for test in skipped_test_ids}

                test_ids = (
                    test_ids & skipped_test_id_set if test_ids else skipped_test_id_set
                )
            case GENERATE_TEST_RESULT_PARAM.SLOWEST:
                totals = DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)

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
                slowest_test_id_set = {test["test_id"] for test in slowest_test_ids}

                test_ids = (
                    test_ids & slowest_test_id_set if test_ids else slowest_test_id_set
                )

    if not first and not last:
        first = 25

    if first is not None and last is not None:
        return ValidationError("First and last can not be used at the same time")
    if after is not None and before is not None:
        return ValidationError("After and before can not be used at the same time")

    query = generate_base_query(
        repoid,
        ordering,
        ordering_direction,
        first,
        after,
        last,
        before,
        branch,
        interval_num_days,
        testsuites,
        term,
        test_ids,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            query.query,
            query.params,
        )
        aggregation_of_test_results = cursor.fetchall()

        rows = [TestResultsRow(*row[:-1]) for row in aggregation_of_test_results]

    return Connection(
        edges=[{"cursor": get_cursor(row, ordering), "node": row} for row in rows],
        total_count=len(rows),
        page_info={
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": get_cursor(rows[0], ordering) if rows else None,
            "end_cursor": get_cursor(rows[-1], ordering) if rows else None,
        },
    )


def percent_diff(
    current_value: int | float, past_value: int | float
) -> int | float | None:
    if past_value == 0:
        return None
    return round((current_value - past_value) / past_value * 100, 5)


def get_percent_change(
    fields: list[str],
    curr_numbers: dict[str, int | float],
    past_numbers: dict[str, int | float],
) -> dict[str, int | float | None]:
    percent_change_fields = {}

    percent_change_fields = {
        f"{field}_percent_change": percent_diff(
            curr_numbers[field], past_numbers[field]
        )
        for field in fields
        if past_numbers.get(field)
    }

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
        total_duration=Sum(
            F("avg_duration_seconds") * (F("pass_count") + F("fail_count"))
        ),
        slowest_tests_duration=slowest_tests_duration,
        skips=Sum("skip_count"),
        fails=Sum("fail_count"),
        total_slow_tests=Value(slow_test_threshold(num_tests)),
    )

    return test_headers[0] if len(test_headers) > 0 else {}


def generate_test_results_aggregates(
    repoid: int, interval: dt.timedelta = dt.timedelta(days=30)
) -> dict[str, float | int | None] | None:
    repo = Repository.objects.get(repoid=repoid)
    since = dt.datetime.now(dt.UTC) - interval

    curr_numbers = get_test_results_aggregate_numbers(repo, since)

    double_time_ago = since - interval

    past_numbers = get_test_results_aggregate_numbers(repo, double_time_ago, since)

    return curr_numbers | get_percent_change(
        [
            "total_duration",
            "slowest_tests_duration",
            "skips",
            "fails",
            "total_slow_tests",
        ],
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
            & (
                Q(start_date__date__lte=until.date())
                & (Q(end_date__date__gt=since.date()) | Q(end_date__isnull=True))
            )
        )

    flake_count = flakes.count()

    test_ids = [flake.test_id for flake in flakes]

    test_rollups = DailyTestRollup.objects.filter(
        repoid=repo.repoid,
        date__gt=since.date(),
        branch=repo.branch,
        test_id__in=test_ids,
    )
    if until:
        test_rollups = test_rollups.filter(date__lte=until.date())

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
    repoid: int, interval: dt.timedelta = dt.timedelta(days=30)
) -> dict[str, int | float | None]:
    repo = Repository.objects.get(repoid=repoid)
    since = dt.datetime.today() - interval

    curr_numbers = get_flake_aggregate_numbers(repo, since)

    double_time_ago = since - interval

    past_numbers = get_flake_aggregate_numbers(repo, double_time_ago, since)

    return curr_numbers | get_percent_change(
        ["flake_count", "flake_rate"],
        curr_numbers,
        past_numbers,
    )
