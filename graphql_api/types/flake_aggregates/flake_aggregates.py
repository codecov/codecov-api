from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

flake_aggregates_bindable = ObjectType("FlakeAggregates")


class FlakeAggregate(TypedDict):
    flake_count: int
    flake_rate: float


@flake_aggregates_bindable.field("flakeCount")
def resolve_flake_count(obj: FlakeAggregate, _: GraphQLResolveInfo) -> int:
    return obj["flake_count"]


@flake_aggregates_bindable.field("flakeRate")
def resolve_flake_rate(obj: FlakeAggregate, _: GraphQLResolveInfo) -> float:
    return obj["flake_rate"]
