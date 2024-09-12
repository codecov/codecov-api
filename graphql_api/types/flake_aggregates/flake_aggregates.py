from ariadne import ObjectType

flake_aggregates_bindable = ObjectType("FlakeAggregates")


@flake_aggregates_bindable.field("flakeCount")
def resolve_name(obj, _) -> int:
    return obj["flake_count"]


@flake_aggregates_bindable.field("flakeRate")
def resolve_updated_at(obj, _) -> float:
    return obj["flake_rate"]
