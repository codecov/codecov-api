import logging
from datetime import timedelta

from ariadne import ObjectType
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.types.enums import OrderingDirection, TestResultsFilterParameter
from graphql_api.types.enums.enum_types import MeasurementInterval
from utils.test_results import (
    GENERATE_TEST_RESULT_PARAM,
    generate_flake_aggregates,
    generate_test_results,
    generate_test_results_aggregates,
    get_flags,
    get_test_suites,
    OrderingParameter,
)

log = logging.getLogger(__name__)

# Bindings for GraphQL types
test_analytics_bindable: ObjectType = ObjectType("TestAnalytics")


@test_analytics_bindable.field("testResults")
async def resolve_test_results(
    repository: Repository,
    info: GraphQLResolveInfo,
    ordering=None,
    filters=None,
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
):
    parameter = (
        convert_test_results_filter_parameter(filters.get("parameter"))
        if filters
        else None
    )
    interval = (
        convert_interval_to_timedelta(filters.get("interval"))
        if filters
        else timedelta(days=30)
    )

    queryset = await sync_to_async(generate_test_results)(
        ordering_param=OrderingParameter(
            ordering=ordering.get("parameter").value,
            ordering_direction=ordering.get("direction").name,
        )
        if ordering
        else None,
        repoid=repository.repoid,
        interval=interval,
        first=first,
        after=after,
        last=last,
        before=before,
        branch=filters.get("branch") if filters else None,
        parameter=parameter,
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
    **_,
):
    return await sync_to_async(generate_test_results_aggregates)(
        repoid=repository.repoid, interval=convert_interval_to_timedelta(interval)
    )


@test_analytics_bindable.field("flakeAggregates")
async def resolve_flake_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    interval: MeasurementInterval | None = None,
    **_,
):
    return await sync_to_async(generate_flake_aggregates)(
        repoid=repository.repoid, interval=convert_interval_to_timedelta(interval)
    )


@test_analytics_bindable.field("testSuites")
async def resolve_test_suites(
    repository: Repository, info: GraphQLResolveInfo, term: str | None = None, **_
):
    return await sync_to_async(get_test_suites)(repository.repoid, term)


@test_analytics_bindable.field("flags")
async def resolve_flags(
    repository: Repository, info: GraphQLResolveInfo, term: str | None = None, **_
):
    return await sync_to_async(get_flags)(repository.repoid, term)


def convert_interval_to_timedelta(interval: MeasurementInterval | None) -> timedelta:
    if interval is None:
        return timedelta(days=30)

    match interval:
        case MeasurementInterval.INTERVAL_1_DAY:
            return timedelta(days=1)
        case MeasurementInterval.INTERVAL_7_DAY:
            return timedelta(days=7)
        case MeasurementInterval.INTERVAL_30_DAY:
            return timedelta(days=30)


def convert_test_results_filter_parameter(
    parameter: TestResultsFilterParameter | None,
) -> GENERATE_TEST_RESULT_PARAM | None:
    if parameter is None:
        return None

    match parameter:
        case TestResultsFilterParameter.FLAKY_TESTS:
            return GENERATE_TEST_RESULT_PARAM.FLAKY
        case TestResultsFilterParameter.FAILED_TESTS:
            return GENERATE_TEST_RESULT_PARAM.FAILED
        case TestResultsFilterParameter.SLOWEST_TESTS:
            return GENERATE_TEST_RESULT_PARAM.SLOWEST
        case TestResultsFilterParameter.SKIPPED_TESTS:
            return GENERATE_TEST_RESULT_PARAM.SKIPPED
