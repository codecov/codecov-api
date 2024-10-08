import logging

from ariadne import ObjectType
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection, TestResultsFilterParameter
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
async def resolve_results(
    repository: Repository,
    info: GraphQLResolveInfo,
    ordering=None,
    filters=None,
    **kwargs,
):
    parameter = None
    generate_test_results_param = None
    if filters:
        parameter = filters.get("parameter")
    match parameter:
        case TestResultsFilterParameter.FLAKY_TESTS:
            generate_test_results_param = GENERATE_TEST_RESULT_PARAM.FLAKY
        case TestResultsFilterParameter.FAILED_TESTS:
            generate_test_results_param = GENERATE_TEST_RESULT_PARAM.FAILED
        case TestResultsFilterParameter.SLOWEST_TESTS:
            generate_test_results_param = GENERATE_TEST_RESULT_PARAM.SLOWEST
        case TestResultsFilterParameter.SKIPPED_TESTS:
            generate_test_results_param = GENERATE_TEST_RESULT_PARAM.SKIPPED

    queryset = await sync_to_async(generate_test_results)(
        repoid=repository.repoid,
        branch=filters.get("branch") if filters else None,
        parameter=generate_test_results_param,
        testsuites=filters.get("test_suites") if filters else None,
        flags=filters.get("flags") if filters else None,
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
):
    return await sync_to_async(generate_test_results_aggregates)(
        repoid=repository.repoid
    )


@test_analytics_bindable.field("flakeAggregates")
async def resolve_flake_aggregates(repository: Repository, info: GraphQLResolveInfo):
    return await sync_to_async(generate_flake_aggregates)(repoid=repository.repoid)
