import logging
from datetime import timedelta

from ariadne import ObjectType
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection, TestResultsFilterParameter
from graphql_api.types.enums.enum_types import MeasurementInterval
from utils.test_results import (
    GENERATE_TEST_RESULT_PARAM,
    generate_flake_aggregates,
    generate_test_results,
    generate_test_results_aggregates,
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
    **kwargs,
):
    parameter = (
        convert_test_results_filter_parameter(filters.get("parameter"))
        if filters
        else None
    )
    history = (
        convert_history_to_timedelta(filters.get("history"))
        if filters
        else timedelta(days=30)
    )

    queryset = await sync_to_async(generate_test_results)(
        repoid=repository.repoid,
        history=history,
        branch=filters.get("branch") if filters else None,
        parameter=parameter,
        testsuites=filters.get("test_suites") if filters else None,
        flags=filters.get("flags") if filters else None,
        term=filters.get("term") if filters else None,
    )

    return await queryset_to_connection(
        queryset,
        ordering=(
            (ordering.get("parameter"), "name")
            if ordering
            else ("avg_duration", "name")
        ),
        ordering_direction=(
            ordering.get("direction") if ordering else OrderingDirection.DESC
        ),
        **kwargs,
    )


@test_analytics_bindable.field("testResultsAggregates")
async def resolve_test_results_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    history: MeasurementInterval | None = None,
    **_,
):
    history = convert_history_to_timedelta(history)
    return await sync_to_async(generate_test_results_aggregates)(
        repoid=repository.repoid, history=history
    )


@test_analytics_bindable.field("flakeAggregates")
async def resolve_flake_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
    history: MeasurementInterval | None = None,
    **_,
):
    history = convert_history_to_timedelta(history)
    return await sync_to_async(generate_flake_aggregates)(
        repoid=repository.repoid, history=history
    )


def convert_history_to_timedelta(interval: MeasurementInterval | None) -> timedelta:
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
