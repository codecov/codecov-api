import datetime as dt
from base64 import b64decode, b64encode
from collections import defaultdict
from dataclasses import dataclass
from math import floor

from django.db import connection
from django.db.models import (
    Avg,
    F,
    Q,
    QuerySet,
    Sum,
    Value,
)
from shared.django_apps.core.models import Repository
from shared.django_apps.reports.models import (
    DailyTestRollup,
    Flake,
    Test,
    TestFlagBridge,
)

from codecov.commands.exceptions import ValidationError
from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsFilterParameter,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)

SLOW_TEST_PERCENTILE = 95

DELIMITER = "|"


def slow_test_threshold(total_tests: int) -> int:
    percentile = (100 - SLOW_TEST_PERCENTILE) / 100
    slow_tests_to_return = floor(percentile * total_tests)
    return min(max(slow_tests_to_return, 1), 100)


@dataclass
class TestResultsQuery:
    query: str
    params: dict[str, int | str | tuple[str, ...]]


@dataclass
class TestResultsRow:
    # the order here must match the order of the fields in the query
    name: str
    test_id: str
    failure_rate: float
    flake_rate: float
    updated_at: dt.datetime
    avg_duration: float
    total_fail_count: int
    total_flaky_fail_count: int
    total_pass_count: int
    total_skip_count: int
    commits_where_fail: int
    last_duration: float


@dataclass
class TestResultsAggregates:
    total_duration: float
    total_duration_percent_change: float | None
    slowest_tests_duration: float
    slowest_tests_duration_percent_change: float | None
    total_slow_tests: int
    total_slow_tests_percent_change: float | None
    fails: int
    fails_percent_change: float | None
    skips: int
    skips_percent_change: float | None


@dataclass
class FlakeAggregates:
    flake_count: int
    flake_count_percent_change: float | None
    flake_rate: float
    flake_rate_percent_change: float | None


@dataclass
class TestResultConnection:
    edges: list[dict[str, str | TestResultsRow]]
    page_info: dict
    total_count: int


def convert_tuple_else_none(
    value: set[str] | list[str] | None,
) -> tuple[str, ...] | None:
    return tuple(value) if value else None


@dataclass
class CursorValue:
    ordered_value: str
    name: str


def decode_cursor(value: str | None) -> CursorValue | None:
    if value is None:
        return None

    split_cursor = b64decode(value.encode("ascii")).decode("utf-8").split(DELIMITER)
    return CursorValue(
        ordered_value=split_cursor[0],
        name=split_cursor[1],
    )


def encode_cursor(row: TestResultsRow, ordering: TestResultsOrderingParameter) -> str:
    return b64encode(
        DELIMITER.join([str(getattr(row, ordering.value)), str(row.name)]).encode(
            "utf-8"
        )
    ).decode("ascii")


def validate(
    interval: int,
    ordering: TestResultsOrderingParameter,
    ordering_direction: OrderingDirection,
    after: str | None,
    before: str | None,
    first: int | None,
    last: int | None,
) -> None:
    if interval not in {1, 7, 30}:
        raise ValidationError(f"Invalid interval: {interval}")

    if not isinstance(ordering_direction, OrderingDirection):
        raise ValidationError(f"Invalid ordering direction: {ordering_direction}")

    if not isinstance(ordering, TestResultsOrderingParameter):
        raise ValidationError(f"Invalid ordering field: {ordering}")

    if first is not None and last is not None:
        raise ValidationError("First and last can not be used at the same time")

    if after is not None and before is not None:
        raise ValidationError("After and before can not be used at the same time")


def generate_base_query(
    repoid: int,
    ordering: TestResultsOrderingParameter,
    ordering_direction: OrderingDirection,
    should_reverse: bool,
    branch: str | None,
    interval: int,
    testsuites: list[str] | None = None,
    term: str | None = None,
    test_ids: set[str] | None = None,
) -> TestResultsQuery:
    term_filter = f"%{term}%" if term else None

    if should_reverse:
        ordering_direction = (
            OrderingDirection.DESC
            if ordering_direction == OrderingDirection.ASC
            else OrderingDirection.ASC
        )

    order_by = (
        f"with_cursor.{ordering.value} {ordering_direction.name}, with_cursor.name"
    )

    params: dict[str, int | str | tuple[str, ...] | None] = {
        "repoid": repoid,
        "interval": f"{interval} days",
        "branch": branch,
        "test_ids": convert_tuple_else_none(test_ids),
        "testsuites": convert_tuple_else_none(testsuites),
        "term": term_filter,
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
		and rd.date >= current_date - interval %(interval)s
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
        SUM(flaky_fail_count) as total_flaky_fail_count,
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
	) as tests_with_commits_that_failed, unnest(cwf) as unnested_cwf group by test_id
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
    COALESCE(rt.computed_name, rt.name) as name,
    results.*
    from
    (
        select failure_rate_cte.*, coalesce(commits_where_fail_cte.failed_commits_count, 0) as commits_where_fail, last_duration_cte.last_duration_seconds as last_duration
        from failure_rate_cte
        full outer join commits_where_fail_cte using (test_id)
        full outer join last_duration_cte using (test_id)
    ) as results join reports_test rt on results.test_id = rt.id
) as with_cursor
order by {order_by}
"""

    return TestResultsQuery(query=base_query, params=filtered_params)


def search_base_query(
    rows: list[TestResultsRow],
    ordering: TestResultsOrderingParameter,
    cursor: CursorValue | None,
    descending: bool = False,
) -> list[TestResultsRow]:
    """
    The reason we have to do this filtering in the application logic is because we need to get the total count of rows that
    match from the base query, but we only want to return the rows from after the cursor, so to avoid doing multiple SQL queries
    to get the total count of rows that match and then filtering in the database we do the filtering here.

    This is a binary search to find the cursor based on the ordering field.

    The base query we get back is not filtered, we need to filter the rows in the application logic here
    so we decode the cursor, which is a value for the ordering field (based on the OrderingParameter) and
    a value for the name field.

    The list of rows we get back from the base query is ordered by the ordering field, then by name, so we
    can do a binary search to find the value corresponding to the cursor.

    When we find the value corresponding to the cursor we return the rows starting from there, and then we filter
    by the page size after we call this function.
    """
    if not cursor:
        return rows

    print(f"descending: {descending}")

    def compare(row: TestResultsRow) -> int:
        # -1 means row value is to the left of the cursor value (search to the right)
        # 0 means row value is equal to cursor value
        # 1 means row value is to the right of the cursor value (search to the left)
        row_value = getattr(row, ordering.value)
        row_value_str = str(row_value)
        cursor_value_str = cursor.ordered_value
        row_is_greater = row_value_str > cursor_value_str
        row_is_less = row_value_str < cursor_value_str
        if descending:
            return row_is_less - row_is_greater
        else:
            return row_is_greater - row_is_less

    left, right = 0, len(rows) - 1
    while left <= right:
        mid = (left + right) // 2
        comparison = compare(rows[mid])

        if comparison == 0:
            if rows[mid].name == cursor.name:
                return rows[mid + 1 :]
            elif rows[mid].name < cursor.name:
                left = mid + 1
            else:
                right = mid - 1
        elif comparison < 0:
            left = mid + 1
        else:
            right = mid - 1

    return rows[left:]


def get_relevant_totals(
    repoid: int, branch: str | None, since: dt.datetime
) -> QuerySet:
    if branch:
        return DailyTestRollup.objects.filter(
            repoid=repoid, date__gt=since, branch=branch
        )
    else:
        return DailyTestRollup.objects.filter(repoid=repoid, date__gt=since)


def generate_test_results(
    ordering: TestResultsOrderingParameter,
    ordering_direction: OrderingDirection,
    repoid: int,
    measurement_interval: MeasurementInterval,
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
    branch: str | None = None,
    parameter: TestResultsFilterParameter | None = None,
    testsuites: list[str] | None = None,
    flags: defaultdict[str, str] | None = None,
    term: str | None = None,
) -> TestResultConnection:
    """
    Function that retrieves aggregated information about all tests in a given repository, for a given time range, optionally filtered by branch name.
    The fields it calculates are: the test failure rate, commits where this test failed, last duration and average duration of the test.

    :param repoid: repoid of the repository we want to calculate aggregates for
    :param branch: optional name of the branch we want to filter on, if this is provided the aggregates calculated will only take into account
        test instances generated on that branch. By default branches will not be filtered and test instances on all branches wil be taken into
        account.
    :param interval: timedelta for filtering test instances used to calculate the aggregates by time, the test instances used will be
        those with a created at larger than now - interval.
    :param testsuites: optional list of testsuite names to filter by, this is done via a union
    :param flags: optional list of flag names to filter by, this is done via a union so if a user specifies multiple flags, we get all tests with any
        of the flags, not tests that have all of the flags
    :returns: queryset object containing list of dictionaries of results

    """
    interval = measurement_interval.value
    validate(interval, ordering, ordering_direction, after, before, first, last)

    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=interval)

    test_ids: set[str] | None = None

    if term is not None:
        totals = get_relevant_totals(repoid, branch, since)

        totals = totals.filter(test__name__icontains=term).values("test_id")

        test_ids = set([test["test_id"] for test in totals])

    if flags is not None:
        bridges = TestFlagBridge.objects.select_related("flag").filter(
            flag__flag_name__in=flags
        )

        filtered_test_ids = set([bridge.test_id for bridge in bridges])  # type: ignore

        test_ids = test_ids & filtered_test_ids if test_ids else filtered_test_ids

    if parameter is not None:
        totals = get_relevant_totals(repoid, branch, since)
        match parameter:
            case TestResultsFilterParameter.FLAKY_TESTS:
                flaky_test_ids = (
                    totals.values("test")
                    .annotate(flaky_fail_count_sum=Sum("flaky_fail_count"))
                    .filter(flaky_fail_count_sum__gt=0)
                    .values("test_id")
                )
                flaky_test_id_set = {test["test_id"] for test in flaky_test_ids}

                test_ids = (
                    test_ids & flaky_test_id_set if test_ids else flaky_test_id_set
                )
            case TestResultsFilterParameter.FAILED_TESTS:
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
            case TestResultsFilterParameter.SKIPPED_TESTS:
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
            case TestResultsFilterParameter.SLOWEST_TESTS:
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
        first = 20

    should_reverse = False if first else True

    query = generate_base_query(
        repoid=repoid,
        ordering=ordering,
        ordering_direction=ordering_direction,
        should_reverse=should_reverse,
        branch=branch,
        interval=interval,
        testsuites=testsuites,
        term=term,
        test_ids=test_ids,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            query.query,
            query.params,
        )
        aggregation_of_test_results = cursor.fetchall()

        rows = [TestResultsRow(*row) for row in aggregation_of_test_results]

    page_size: int = first or last or 20

    cursor_value = decode_cursor(after) if after else decode_cursor(before)
    print(f"cursor_value: {cursor_value}")
    descending = ordering_direction == OrderingDirection.DESC
    search_rows = search_base_query(
        rows,
        ordering,
        cursor_value,
        descending=descending,
    )
    print(f"search_rows: {search_rows}")

    page: list[dict[str, str | TestResultsRow]] = [
        {"cursor": encode_cursor(row, ordering), "node": row}
        for i, row in enumerate(search_rows)
        if i < page_size
    ]

    return TestResultConnection(
        edges=page,
        total_count=len(rows),
        page_info={
            "has_next_page": True if first and len(search_rows) > first else False,
            "has_previous_page": True if last and len(search_rows) > last else False,
            "start_cursor": page[0]["cursor"] if page else None,
            "end_cursor": page[-1]["cursor"] if page else None,
        },
    )


def percent_diff(current_value: int | float, past_value: int | float) -> float | None:
    if past_value == 0:
        return None
    return round((current_value - past_value) / past_value * 100, 5)


@dataclass
class TestResultsAggregateNumbers:
    total_duration: float
    slowest_tests_duration: float
    skips: int
    fails: int
    total_slow_tests: int


@dataclass
class FlakeAggregateNumbers:
    flake_count: int
    flake_rate: float


def test_results_aggregates_from_numbers(
    curr_numbers: TestResultsAggregateNumbers | None,
    past_numbers: TestResultsAggregateNumbers | None,
) -> TestResultsAggregates | None:
    if curr_numbers is None:
        return None
    if past_numbers is None:
        return TestResultsAggregates(
            total_duration=curr_numbers.total_duration,
            total_duration_percent_change=None,
            slowest_tests_duration=curr_numbers.slowest_tests_duration,
            slowest_tests_duration_percent_change=None,
            total_slow_tests=curr_numbers.total_slow_tests,
            total_slow_tests_percent_change=None,
            fails=curr_numbers.fails,
            fails_percent_change=None,
            skips=curr_numbers.skips,
            skips_percent_change=None,
        )
    else:
        return TestResultsAggregates(
            total_duration=curr_numbers.total_duration,
            total_duration_percent_change=percent_diff(
                curr_numbers.total_duration,
                past_numbers.total_duration,
            ),
            slowest_tests_duration=curr_numbers.slowest_tests_duration,
            slowest_tests_duration_percent_change=percent_diff(
                curr_numbers.slowest_tests_duration,
                past_numbers.slowest_tests_duration,
            ),
            skips=curr_numbers.skips,
            skips_percent_change=percent_diff(
                curr_numbers.skips,
                past_numbers.skips,
            ),
            fails=curr_numbers.fails,
            fails_percent_change=percent_diff(
                curr_numbers.fails,
                past_numbers.fails,
            ),
            total_slow_tests=curr_numbers.total_slow_tests,
            total_slow_tests_percent_change=percent_diff(
                curr_numbers.total_slow_tests,
                past_numbers.total_slow_tests,
            ),
        )


def flake_aggregates_from_numbers(
    curr_numbers: FlakeAggregateNumbers | None,
    past_numbers: FlakeAggregateNumbers | None,
) -> FlakeAggregates | None:
    if curr_numbers is None:
        return None

    return FlakeAggregates(
        flake_count=curr_numbers.flake_count,
        flake_count_percent_change=percent_diff(
            curr_numbers.flake_count, past_numbers.flake_count
        )
        if past_numbers
        else None,
        flake_rate=curr_numbers.flake_rate,
        flake_rate_percent_change=percent_diff(
            curr_numbers.flake_rate,
            past_numbers.flake_rate,
        )
        if past_numbers
        else None,
    )


def get_test_results_aggregate_numbers(
    repo: Repository, since: dt.datetime, until: dt.datetime | None = None
) -> TestResultsAggregateNumbers | None:
    totals = DailyTestRollup.objects.filter(
        repoid=repo.repoid, date__gte=since, branch=repo.branch
    )

    if until:
        totals = totals.filter(date__lt=until)

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

    if len(test_headers) == 0:
        return None
    else:
        headers = test_headers[0]
        return TestResultsAggregateNumbers(
            total_duration=headers["total_duration"] or 0.0,
            slowest_tests_duration=headers["slowest_tests_duration"] or 0.0,
            skips=headers["skips"] or 0,
            fails=headers["fails"] or 0,
            total_slow_tests=headers["total_slow_tests"] or 0,
        )


def generate_test_results_aggregates(
    repoid: int, interval: int
) -> TestResultsAggregates | None:
    repo = Repository.objects.get(repoid=repoid)
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=interval)

    curr_numbers = get_test_results_aggregate_numbers(repo, since)

    double_time_ago = since - dt.timedelta(days=interval)

    past_numbers = get_test_results_aggregate_numbers(repo, double_time_ago, since)

    aggregates_with_percentage: TestResultsAggregates | None = (
        test_results_aggregates_from_numbers(
            curr_numbers,
            past_numbers,
        )
    )

    return aggregates_with_percentage


def get_flake_aggregate_numbers(
    repo: Repository, since: dt.datetime, until: dt.datetime | None = None
) -> FlakeAggregateNumbers:
    if until is None:
        flakes = Flake.objects.filter(
            Q(repository_id=repo.repoid)
            & (Q(end_date__isnull=True) | Q(end_date__date__gte=since.date()))
        )
    else:
        flakes = Flake.objects.filter(
            Q(repository_id=repo.repoid)
            & (
                Q(start_date__date__lt=until.date())
                & (Q(end_date__date__gte=since.date()) | Q(end_date__isnull=True))
            )
        )

    flake_count = flakes.count()

    test_ids = [flake.test_id for flake in flakes]  # type: ignore

    test_rollups = DailyTestRollup.objects.filter(
        repoid=repo.repoid,
        date__gte=since.date(),
        branch=repo.branch,
        test_id__in=test_ids,
    )
    if until:
        test_rollups = test_rollups.filter(date__lt=until.date())

    if len(test_rollups) == 0:
        return FlakeAggregateNumbers(flake_count=0, flake_rate=0.0)

    numerator = 0
    denominator = 0
    for test_rollup in test_rollups:
        numerator += test_rollup.flaky_fail_count
        denominator += test_rollup.fail_count + test_rollup.pass_count

    if denominator == 0:
        flake_rate = 0.0
    else:
        flake_rate = numerator / denominator

    return FlakeAggregateNumbers(flake_count=flake_count, flake_rate=flake_rate)


def generate_flake_aggregates(repoid: int, interval: int) -> FlakeAggregates | None:
    repo = Repository.objects.get(repoid=repoid)
    since = dt.datetime.today() - dt.timedelta(days=interval)

    curr_numbers = get_flake_aggregate_numbers(repo, since)

    double_time_ago = since - dt.timedelta(days=interval)

    past_numbers = get_flake_aggregate_numbers(repo, double_time_ago, since)

    return flake_aggregates_from_numbers(curr_numbers, past_numbers)


def get_test_suites(repoid: int, term: str | None = None) -> list[str]:
    if term:
        return list(
            Test.objects.filter(repository_id=repoid, testsuite__icontains=term)
            .values_list("testsuite", flat=True)
            .distinct()
        )
    else:
        return list(
            Test.objects.filter(repository_id=repoid)
            .values_list("testsuite", flat=True)
            .distinct()
        )


def get_flags(repoid: int, term: str | None = None) -> list[str]:
    if term:
        return list(
            TestFlagBridge.objects.filter(
                test__repository_id=repoid, flag__flag_name__icontains=term
            )
            .select_related("flag")
            .values_list("flag__flag_name", flat=True)
            .distinct()
        )
    else:
        return list(
            TestFlagBridge.objects.filter(test__repository_id=repoid)
            .select_related("flag")
            .values_list("flag__flag_name", flat=True)
            .distinct()
        )
