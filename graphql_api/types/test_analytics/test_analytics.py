import logging

from ariadne import ObjectType, convert_kwargs_to_snake_case
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from utils.test_results import (
    aggregate_test_results,
    generate_flake_aggregates,
    generate_test_results_aggregates,
)

log = logging.getLogger(__name__)

# Bindings for GraphQL types
test_analytics_bindable: ObjectType = ObjectType("TestAnalytics")


@test_analytics_bindable.field("results")
@convert_kwargs_to_snake_case
async def resolve_test_results(
    repository: Repository,
    info: GraphQLResolveInfo,
    ordering=None,
    filters=None,
    **kwargs,
):
    queryset = await sync_to_async(aggregate_test_results)(
        repoid=repository.repoid, branch=filters.get("branch") if filters else None
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
@convert_kwargs_to_snake_case
async def resolve_test_results_aggregates(
    repository: Repository,
    info: GraphQLResolveInfo,
):
    return await sync_to_async(generate_test_results_aggregates)(
        repoid=repository.repoid
    )


@test_analytics_bindable.field("flakeAggregates")
@convert_kwargs_to_snake_case
async def resolve_flake_aggregates(repository: Repository, info: GraphQLResolveInfo):
    return await sync_to_async(generate_flake_aggregates)(repoid=repository.repoid)
