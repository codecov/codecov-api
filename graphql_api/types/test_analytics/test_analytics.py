import logging
from typing import Any, TypedDict

from ariadne import ObjectType
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsFilterParameter,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval
from utils.test_results import (
    FlakeAggregates,
    TestResultConnection,
    TestResultsAggregates,
    generate_flake_aggregates,
    generate_test_results,
    generate_test_results_aggregates,
    get_flags,
    get_test_suites,
)

log = logging.getLogger(__name__)


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
        repoid=repository.repoid, interval=interval.value if interval else 30
    )


@test_analytics_bindable.field("flakeAggregates")
async def resolve_flake_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    interval: MeasurementInterval | None = None,
    **_: Any,
) -> FlakeAggregates | None:
    return await sync_to_async(generate_flake_aggregates)(
        repoid=repository.repoid, interval=interval.value if interval else 30
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
