import datetime as dt
import logging
from base64 import b64decode, b64encode
from dataclasses import dataclass
from typing import Any, TypedDict

import polars as pl
from ariadne import ObjectType
from graphql.type.definition import GraphQLResolveInfo
from shared.django_apps.core.models import Repository

from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsFilterParameter,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval
from graphql_api.types.flake_aggregates.flake_aggregates import (
    FlakeAggregates,
    generate_flake_aggregates,
)
from graphql_api.types.test_results_aggregates.test_results_aggregates import (
    TestResultsAggregates,
    generate_test_results_aggregates,
)
from utils.test_results import get_results

log = logging.getLogger(__name__)

INTERVAL_30_DAY = 30
INTERVAL_7_DAY = 7
INTERVAL_1_DAY = 1


@dataclass
class TestResultsRow:
    # the order here must match the order of the fields in the query
    name: str
    test_id: str
    testsuite: str | None
    flags: list[str]
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
class TestResultConnection:
    edges: list[dict[str, str | TestResultsRow]]
    page_info: dict
    total_count: int


DELIMITER = "|"


@dataclass
class CursorValue:
    ordered_value: float | int | dt.datetime | str
    name: str


def decode_cursor(
    value: str | None, ordering: TestResultsOrderingParameter
) -> CursorValue | None:
    if value is None:
        return None

    split_cursor = b64decode(value.encode("ascii")).decode("utf-8").split(DELIMITER)
    ordered_value: str = split_cursor[0]
    name: str = split_cursor[1]
    match ordering:
        case (
            TestResultsOrderingParameter.AVG_DURATION
            | TestResultsOrderingParameter.FLAKE_RATE
            | TestResultsOrderingParameter.FAILURE_RATE
            | TestResultsOrderingParameter.LAST_DURATION
        ):
            return CursorValue(ordered_value=float(ordered_value), name=name)
        case TestResultsOrderingParameter.COMMITS_WHERE_FAIL:
            return CursorValue(ordered_value=int(ordered_value), name=name)
        case TestResultsOrderingParameter.UPDATED_AT:
            return CursorValue(
                ordered_value=dt.datetime.fromisoformat(ordered_value), name=name
            )

    raise ValueError(f"Invalid ordering field: {ordering}")


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
    if interval not in {INTERVAL_1_DAY, INTERVAL_7_DAY, INTERVAL_30_DAY}:
        raise ValidationError(f"Invalid interval: {interval}")

    if not isinstance(ordering_direction, OrderingDirection):
        raise ValidationError(f"Invalid ordering direction: {ordering_direction}")

    if not isinstance(ordering, TestResultsOrderingParameter):
        raise ValidationError(f"Invalid ordering field: {ordering}")

    if first is not None and last is not None:
        raise ValidationError("First and last can not be used at the same time")

    if after is not None and before is not None:
        raise ValidationError("After and before can not be used at the same time")


def ordering_expression(
    ordering: TestResultsOrderingParameter, cursor_value: CursorValue, is_forward: bool
) -> pl.Expr:
    if is_forward:
        ordering_expression = (pl.col(ordering.value) > cursor_value.ordered_value) | (
            (pl.col(ordering.value) == cursor_value.ordered_value)
            & (pl.col("name") > cursor_value.name)
        )
    else:
        ordering_expression = (pl.col(ordering.value) < cursor_value.ordered_value) | (
            (pl.col(ordering.value) == cursor_value.ordered_value)
            & (pl.col("name") > cursor_value.name)
        )
    return ordering_expression


def generate_test_results(
    ordering: TestResultsOrderingParameter,
    ordering_direction: OrderingDirection,
    repoid: int,
    measurement_interval: MeasurementInterval,
    *,
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
    branch: str | None = None,
    parameter: TestResultsFilterParameter | None = None,
    testsuites: list[str] | None = None,
    flags: list[str] | None = None,
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
    repo = Repository.objects.get(repoid=repoid)
    if branch is None:
        branch = repo.branch
    interval = measurement_interval.value
    validate(interval, ordering, ordering_direction, after, before, first, last)

    table = get_results(repoid, branch, interval)

    if table is None:
        return TestResultConnection(
            edges=[],
            total_count=0,
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": None,
                "end_cursor": None,
            },
        )

    if term:
        table = table.filter(pl.col("name").str.starts_with(term))

    if testsuites:
        table = table.filter(
            pl.col("testsuite").is_not_null() & pl.col("testsuite").is_in(testsuites)
        )

    if flags:
        table = table.filter(
            pl.col("flags").is_not_null()
            & pl.col("flags").list.eval(pl.element().is_in(flags)).list.any()
        )

    match parameter:
        case TestResultsFilterParameter.FAILED_TESTS:
            table = table.filter(pl.col("total_fail_count") > 0)
        case TestResultsFilterParameter.FLAKY_TESTS:
            table = table.filter(pl.col("total_flaky_fail_count") > 0)
        case TestResultsFilterParameter.SKIPPED_TESTS:
            table = table.filter(
                (pl.col("total_skip_count") > 0) & (pl.col("total_pass_count") == 0)
            )
        case TestResultsFilterParameter.SLOWEST_TESTS:
            table = table.filter(
                pl.col("avg_duration") >= pl.col("avg_duration").quantile(0.95)
            ).top_k(
                min(100, max(table.height // 20, 1)), by=pl.col("avg_duration")
            )  # the top k operation here is to make sure we don't show too many slowest tests in the case of a low sample size

    total_count = table.height

    if after or before:
        comparison_direction = (ordering_direction == OrderingDirection.ASC) == (
            bool(after)
        )
        cursor_value = (
            decode_cursor(after, ordering) if after else decode_cursor(before, ordering)
        )
        if cursor_value:
            table = table.filter(
                ordering_expression(ordering, cursor_value, comparison_direction)
            )

    table = table.sort(
        [ordering.value, "name"],
        descending=[ordering_direction == OrderingDirection.DESC, False],
    )

    if first:
        page_elements = table.slice(0, first)
    elif last:
        page_elements = table.slice(-last, last)
    else:
        page_elements = table

    rows = [TestResultsRow(**row) for row in page_elements.rows(named=True)]

    page: list[dict[str, str | TestResultsRow]] = [
        {"cursor": encode_cursor(row, ordering), "node": row} for row in rows
    ]

    return TestResultConnection(
        edges=page,
        total_count=total_count,
        page_info={
            "has_next_page": True if first and len(table) > first else False,
            "has_previous_page": True if last and len(table) > last else False,
            "start_cursor": page[0]["cursor"] if page else None,
            "end_cursor": page[-1]["cursor"] if page else None,
        },
    )


def get_test_suites(
    repoid: int, term: str | None = None, interval: int = 30
) -> list[str]:
    repo = Repository.objects.get(repoid=repoid)

    table = get_results(repoid, repo.branch, interval)
    if table is None:
        return []

    testsuites = table.select(pl.col("testsuite")).unique()

    if term:
        testsuites = testsuites.filter(pl.col("testsuite").str.starts_with(term))

    return testsuites.to_series().drop_nulls().to_list() or []


def get_flags(repoid: int, term: str | None = None, interval: int = 30) -> list[str]:
    repo = Repository.objects.get(repoid=repoid)

    table = get_results(repoid, repo.branch, interval)
    if table is None:
        return []

    flags = table.select(pl.col("flags").explode()).unique()

    if term:
        flags = flags.filter(pl.col("flags").str.starts_with(term))

    return flags.to_series().drop_nulls().to_list() or []


class TestResultsOrdering(TypedDict):
    parameter: TestResultsOrderingParameter
    direction: OrderingDirection


class TestResultsFilters(TypedDict):
    parameter: TestResultsFilterParameter | None
    interval: MeasurementInterval
    branch: str | None
    test_suites: list[str] | None
    flags: list[str] | None
    term: str | None


# Bindings for GraphQL types
test_analytics_bindable: ObjectType = ObjectType("TestAnalytics")


@test_analytics_bindable.field("testResults")
async def resolve_test_results(
    repository: Repository,
    info: GraphQLResolveInfo,
    ordering: TestResultsOrdering | None = None,
    filters: TestResultsFilters | None = None,
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
) -> TestResultConnection:
    queryset = await sync_to_async(generate_test_results)(
        ordering=ordering.get("parameter", TestResultsOrderingParameter.AVG_DURATION)
        if ordering
        else TestResultsOrderingParameter.AVG_DURATION,
        ordering_direction=ordering.get("direction", OrderingDirection.DESC)
        if ordering
        else OrderingDirection.DESC,
        repoid=repository.repoid,
        measurement_interval=filters.get(
            "interval", MeasurementInterval.INTERVAL_30_DAY
        )
        if filters
        else MeasurementInterval.INTERVAL_30_DAY,
        first=first,
        after=after,
        last=last,
        before=before,
        branch=filters.get("branch") if filters else None,
        parameter=filters.get("parameter") if filters else None,
        testsuites=filters.get("test_suites") if filters else None,
        flags=filters.get("flags") if filters else None,
        term=filters.get("term") if filters else None,
    )

    return queryset


@test_analytics_bindable.field("testResultsAggregates")
async def resolve_test_results_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    interval: MeasurementInterval | None = None,
    **_: Any,
) -> TestResultsAggregates | None:
    return await sync_to_async(generate_test_results_aggregates)(
        repoid=repository.repoid,
        interval=interval if interval else MeasurementInterval.INTERVAL_30_DAY,
    )


@test_analytics_bindable.field("flakeAggregates")
async def resolve_flake_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    interval: MeasurementInterval | None = None,
    **_: Any,
) -> FlakeAggregates | None:
    return await sync_to_async(generate_flake_aggregates)(
        repoid=repository.repoid,
        interval=interval if interval else MeasurementInterval.INTERVAL_30_DAY,
    )


@test_analytics_bindable.field("testSuites")
async def resolve_test_suites(
    repository: Repository, info: GraphQLResolveInfo, term: str | None = None, **_: Any
) -> list[str]:
    return await sync_to_async(get_test_suites)(repository.repoid, term)


@test_analytics_bindable.field("flags")
async def resolve_flags(
    repository: Repository, info: GraphQLResolveInfo, term: str | None = None, **_: Any
) -> list[str]:
    return await sync_to_async(get_flags)(repository.repoid, term)
