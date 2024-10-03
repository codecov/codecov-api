import logging
from dataclasses import dataclass
from typing import Any, Optional, Union

from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from graphql.type.definition import GraphQLResolveInfo

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from graphql_api.types.errors.errors import NotFoundError
from utils.test_results import aggregate_test_results

log = logging.getLogger(__name__)

# Bindings for GraphQL types
test_analytics_bindable: ObjectType = ObjectType("TestAnalytics")
test_analytics_result_bindable: UnionType = UnionType("TestAnalyticsResult")


# TestAnalyticsProps is information passed from parent resolver (repository)
# to the test analytics resolver
@dataclass
class TestAnalyticsProps:
    repository: Repository


@test_analytics_result_bindable.type_resolver
def resolve_test_analytics_result_type(
    obj: Union[TestAnalyticsProps, NotFoundError], *_: Any
) -> Optional[str]:
    if isinstance(obj, TestAnalyticsProps):
        return "TestAnalyticsProps"
    elif isinstance(obj, NotFoundError):
        return "NotFoundError"
    return None


@test_analytics_bindable.field("testResults")
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
