from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from utils.test_results import FlakeAggregates

flake_aggregates_bindable = ObjectType("FlakeAggregates")


@flake_aggregates_bindable.field("flakeCount")
def resolve_flake_count(obj: FlakeAggregates, _: GraphQLResolveInfo) -> int:
    return obj.flake_count


@flake_aggregates_bindable.field("flakeCountPercentChange")
def resolve_flake_count_percent_change(
    obj: FlakeAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.flake_count_percent_change


@flake_aggregates_bindable.field("flakeRate")
def resolve_flake_rate(obj: FlakeAggregates, _: GraphQLResolveInfo) -> float:
    return obj.flake_rate


@flake_aggregates_bindable.field("flakeRatePercentChange")
def resolve_flake_rate_percent_change(
    obj: FlakeAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.flake_rate_percent_change
