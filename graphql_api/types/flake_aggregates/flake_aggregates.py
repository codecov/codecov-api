from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

flake_aggregates_bindable = ObjectType("FlakeAggregates")


class FlakeAggregate(TypedDict):
    flake_count: int
    flake_count_percent_change: float | None
    flake_rate: float
    flake_rate_percent_change: float | None


@flake_aggregates_bindable.field("flakeCount")
def resolve_flake_count(obj: FlakeAggregate, _: GraphQLResolveInfo) -> int:
    return obj["flake_count"]

@flake_aggregates_bindable.field("flakeCountPercentChange")
def resolve_flake_count_percent_change(obj: FlakeAggregate, _: GraphQLResolveInfo) -> float | None:
    return obj.get("flake_count_percent_change")


@flake_aggregates_bindable.field("flakeRate")
def resolve_flake_rate(obj: FlakeAggregate, _: GraphQLResolveInfo) -> float:
    return obj["flake_rate"]

@flake_aggregates_bindable.field("flakeRatePercentChange")
def resolve_flake_rate_percent_change(obj: FlakeAggregate, _: GraphQLResolveInfo) -> float | None:
    return obj.get("flake_rate_percent_change")
