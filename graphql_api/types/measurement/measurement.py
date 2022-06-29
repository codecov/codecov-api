from datetime import datetime

from ariadne import ObjectType

measurement_bindable = ObjectType("Measurement")


@measurement_bindable.field("timestamp")
def resolve_timestamp(measurement: dict, info) -> datetime:
    return measurement["timestamp_bin"]


@measurement_bindable.field("avg")
def resolve_avg(measurement: dict, info) -> float:
    return measurement["avg"]


@measurement_bindable.field("min")
def resolve_min(measurement: dict, info) -> float:
    return measurement["min"]


@measurement_bindable.field("max")
def resolve_max(measurement: dict, info) -> float:
    return measurement["max"]
